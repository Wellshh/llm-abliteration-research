"""Reversible postblock projection with explicit padding, decode and patch order.

Positions are (batch row, absolute padded-sequence index), never token IDs.
Only selected positions are cached on CPU; all valid tokens can be projected.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence


@dataclass(frozen=True)
class PatchSpec:
    layer: int
    positions: tuple[tuple[int, int], ...]
    values: Any  # torch.Tensor [number of positions, hidden size]
    order: Literal["before_projection", "after_projection"] = "after_projection"
    donor_id: str = "unspecified"


def transformer_blocks(model: Any) -> list[Any]:
    if not hasattr(model, "model") or not hasattr(model.model, "layers"):
        raise ValueError("unsupported module topology: expected model.model.layers")
    blocks = list(model.model.layers)
    if not blocks or len(blocks) != model.config.num_hidden_layers:
        raise ValueError("actual transformer blocks disagree with model config")
    return blocks


def rank_one_projection(hidden: Any, direction: Any, alpha: float, valid_mask: Any) -> Any:
    """Accumulate projection in FP32 and leave padding exactly unchanged."""
    import torch
    if alpha == 0:
        return hidden
    unit = direction.detach().to(device=hidden.device, dtype=torch.float32)
    unit = unit / torch.linalg.vector_norm(unit)
    fp32 = hidden.float()
    projected = fp32 - float(alpha) * (fp32 @ unit).unsqueeze(-1) * unit
    return torch.where(valid_mask.unsqueeze(-1), projected.to(hidden.dtype), hidden)


class PostBlockHooks:
    """One configuration at a time; context exit always removes registered hooks.

    For generation, the model forward must provide its two-dimensional binary
    attention mask. Dynamic KV decode is handled from its current length; an
    explicit cache_position is honored when supplied. No padding is patched.
    """

    def __init__(self, model: Any, direction: Any = None, alpha: float = 0.0,
                 patches: Sequence[PatchSpec] = (),
                 capture_positions: Mapping[int, Sequence[tuple[int, int]]] | None = None,
                 layers: Sequence[int] | None = None, max_capture_positions: int = 64) -> None:
        import torch
        self.model = model
        self.blocks = transformer_blocks(model)
        self.layers = tuple(range(len(self.blocks))) if layers is None else tuple(layers)
        if len(set(self.layers)) != len(self.layers) or any(i < 0 or i >= len(self.blocks) for i in self.layers):
            raise ValueError("invalid or duplicate projection layer")
        if not isinstance(alpha, (float, int)) or not 0 <= alpha <= 1:
            raise ValueError("alpha must lie in [0, 1]")
        self.alpha, self.direction = float(alpha), direction
        if self.alpha and direction is None:
            raise ValueError("nonzero intervention needs a direction")
        if direction is not None:
            if direction.ndim != 1 or direction.numel() != model.config.hidden_size:
                raise ValueError("direction must have shape [actual hidden size]")
            if not torch.isfinite(direction).all() or (self.alpha and torch.linalg.vector_norm(direction.float()) == 0):
                raise ValueError("projection direction must be finite and nonzero")
        self.patches = tuple(patches)
        seen: set[tuple[int, str, int, int]] = set()
        for patch in self.patches:
            if patch.layer < 0 or patch.layer >= len(self.blocks) or patch.order not in {"before_projection", "after_projection"}:
                raise ValueError("invalid patch layer/order")
            if tuple(patch.values.shape) != (len(patch.positions), model.config.hidden_size):
                raise ValueError("patch values do not match positions and actual hidden size")
            if len(patch.positions) > max_capture_positions or not torch.isfinite(patch.values).all():
                raise ValueError("patch exceeds selected-position budget or contains nonfinite values")
            for row, position in patch.positions:
                key = (patch.layer, patch.order, row, position)
                if row < 0 or position < 0 or key in seen:
                    raise ValueError("invalid or duplicate patch position")
                seen.add(key)
        self.capture_positions = {layer: tuple(positions) for layer, positions in (capture_positions or {}).items()}
        for layer, positions in self.capture_positions.items():
            if layer < 0 or layer >= len(self.blocks) or len(positions) > max_capture_positions:
                raise ValueError("invalid capture layer or selected-position budget exceeded")
            if len(set(positions)) != len(positions) or any(b < 0 or p < 0 for b, p in positions):
                raise ValueError("invalid or duplicate capture positions")
        self.captures: dict[int, dict[tuple[int, int], Any]] = {}
        self.handles: list[Any] = []
        self.mask: Any = None
        self.positions: Any = None
        self.forward_count = 0
        self.decode_forward_count = 0
        self.projected_valid_tokens = 0
        self.patch_applications: list[dict[str, Any]] = []

    def _before_forward(self, module: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        import torch
        mask = kwargs.get("attention_mask")
        if mask is None or mask.ndim != 2 or not torch.all((mask == 0) | (mask == 1)):
            raise ValueError("hooks require an explicit two-dimensional binary attention_mask")
        inputs = kwargs.get("input_ids")
        if inputs is None:
            inputs = kwargs.get("inputs_embeds")
        if inputs is None and args:
            inputs = args[0]
        if inputs is None or inputs.ndim < 2 or inputs.shape[0] != mask.shape[0]:
            raise ValueError("cannot establish input batch/sequence dimensions")
        query_length = inputs.shape[1]
        positions = kwargs.get("cache_position")
        if positions is None:
            start = mask.shape[1] - query_length
            positions = torch.arange(start, mask.shape[1], device=mask.device)
        if (positions.ndim != 1 or positions.numel() != query_length
                or torch.any(positions < 0) or torch.any(positions >= mask.shape[1])):
            raise ValueError("unsupported cache_position/attention-mask alignment")
        self.mask = mask[:, positions.long()].bool()
        self.positions = positions.detach().cpu().tolist()
        self.forward_count += 1
        if query_length == 1 and mask.shape[1] > 1:
            self.decode_forward_count += 1

    def _patch(self, hidden: Any, layer: int, order: str) -> Any:
        output = hidden
        positions = {absolute: local for local, absolute in enumerate(self.positions)}
        for patch in self.patches:
            if patch.layer != layer or patch.order != order:
                continue
            for value_index, (row, absolute) in enumerate(patch.positions):
                if absolute not in positions:
                    continue  # Applies only to the forward containing this absolute token.
                local = positions[absolute]
                if row >= hidden.shape[0]:
                    raise ValueError("patch batch index is outside the current batch")
                if not self.mask[row, local]:
                    raise ValueError("patch requested a padding position")
                if output is hidden:
                    output = hidden.clone()
                output[row, local] = patch.values[value_index].to(device=hidden.device, dtype=hidden.dtype)
                self.patch_applications.append({"layer": layer, "batch": row, "absolute_position": absolute,
                    "order": order, "donor_id": patch.donor_id,
                    "future_projection_remains_active": bool(self.alpha and any(i > layer for i in self.layers))})
        return output

    def _after_block(self, layer: int, output: Any) -> Any:
        import torch
        hidden = output[0] if isinstance(output, tuple) else output
        if not torch.is_tensor(hidden) or hidden.ndim != 3:
            raise ValueError("unsupported transformer block output")
        if self.mask is None or tuple(hidden.shape[:2]) != tuple(self.mask.shape):
            raise ValueError("block token shape does not match model input mask")
        value = self._patch(hidden, layer, "before_projection")
        if layer in self.layers:
            value = rank_one_projection(value, self.direction, self.alpha, self.mask.to(hidden.device))
            if self.alpha:
                self.projected_valid_tokens += int(self.mask.sum().item())
        value = self._patch(value, layer, "after_projection")
        positions = {absolute: local for local, absolute in enumerate(self.positions)}
        for row, absolute in self.capture_positions.get(layer, ()):
            if absolute not in positions:
                continue
            local = positions[absolute]
            if row >= value.shape[0] or not self.mask[row, local]:
                raise ValueError("capture requested padding or a nonexistent batch row")
            self.captures.setdefault(layer, {})[(row, absolute)] = value[row, local].detach().to("cpu", copy=True)
        if value is hidden:
            return output
        return (value, *output[1:]) if isinstance(output, tuple) else value

    def __enter__(self) -> "PostBlockHooks":
        if self.handles or getattr(self.model, "_minicpm_research_hook_active", False):
            raise ValueError("only one intervention configuration can be active")
        self.model._minicpm_research_hook_active = True
        try:
            self.handles.append(self.model.register_forward_pre_hook(self._before_forward, with_kwargs=True))
            for layer, block in enumerate(self.blocks):
                self.handles.append(block.register_forward_hook(
                    lambda module, args, output, index=layer: self._after_block(index, output)))
        except BaseException:
            self.close()
            raise
        return self

    def close(self) -> None:
        for handle in reversed(self.handles):
            handle.remove()
        self.handles.clear()
        self.model._minicpm_research_hook_active = False
        self.mask = self.positions = None

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def manifest(self) -> dict[str, Any]:
        return {"protocol": "postblock-rank1-runtime", "alpha": self.alpha,
                "projection_layers": list(self.layers), "accumulation_dtype": "float32",
                "primary_mutates_weights": False, "applies_to_padding": False,
                "position_convention": "batch_row_and_absolute_padded_sequence_index",
                "capture_stage": "after_patch_and_projection", "capture_storage": "selected_positions_cpu",
                "forward_count": self.forward_count, "decode_forward_count": self.decode_forward_count,
                "projected_valid_tokens_across_layers": self.projected_valid_tokens,
                "patch_applications": list(self.patch_applications)}
