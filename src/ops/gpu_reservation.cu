#include <cuda_runtime.h>

#include <atomic>
#include <cerrno>
#include <chrono>
#include <cmath>
#include <csignal>
#include <cstring>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <sys/prctl.h>
#include <unistd.h>

namespace {

std::atomic<bool> stop_requested{false};
constexpr char kProcessName[] = "autoplacer-RL";

void handle_signal(int) { stop_requested.store(true); }

void set_process_name() {
  if (prctl(PR_SET_NAME, kProcessName, 0, 0, 0) != 0) {
    throw std::runtime_error(std::string("prctl(PR_SET_NAME): ") +
                             std::strerror(errno));
  }
}

void check_cuda(cudaError_t result, const char* operation) {
  if (result != cudaSuccess) {
    throw std::runtime_error(std::string(operation) + ": " +
                             cudaGetErrorString(result));
  }
}

std::uint64_t gib_to_bytes(double gib) {
  if (!std::isfinite(gib) || gib <= 0.0) {
    throw std::invalid_argument("GiB values must be finite and positive");
  }
  constexpr double bytes_per_gib = 1073741824.0;
  const double bytes = gib * bytes_per_gib;
  if (bytes > static_cast<double>(UINT64_MAX)) {
    throw std::overflow_error("GiB value is too large");
  }
  return static_cast<std::uint64_t>(bytes);
}

std::string now_iso8601() {
  const auto now = std::chrono::system_clock::now();
  const std::time_t value = std::chrono::system_clock::to_time_t(now);
  std::tm local{};
  localtime_r(&value, &local);
  std::ostringstream out;
  out << std::put_time(&local, "%Y-%m-%dT%H:%M:%S%z");
  return out.str();
}

std::string device_uuid() {
  cudaDeviceProp properties{};
  check_cuda(cudaGetDeviceProperties(&properties, 0),
             "cudaGetDeviceProperties");
  std::ostringstream out;
  out << "GPU-" << std::hex << std::setfill('0');
  for (int i = 0; i < 16; ++i) {
    out << std::setw(2)
        << static_cast<unsigned int>(
               static_cast<unsigned char>(properties.uuid.bytes[i]));
    if (i == 3 || i == 5 || i == 7 || i == 9) out << '-';
  }
  return out.str();
}

void append_event(const std::string& path, const std::string& event,
                  const std::string& uuid, std::uint64_t allocated_bytes,
                  std::uint64_t free_bytes, std::uint64_t total_bytes,
                  const std::string& reason = "") {
  std::ofstream log(path, std::ios::app);
  if (!log) throw std::runtime_error("cannot open log: " + path);
  log << "{\"timestamp\":\"" << now_iso8601() << "\",\"event\":\""
      << event << "\",\"pid\":" << getpid()
      << ",\"process_name\":\"" << kProcessName
      << "\",\"gpu_uuid\":\"" << uuid
      << "\",\"allocated_bytes\":" << allocated_bytes
      << ",\"free_bytes\":" << free_bytes << ",\"total_bytes\":"
      << total_bytes;
  if (!reason.empty()) log << ",\"reason\":\"" << reason << "\"";
  log << "}\n";
  log.flush();
  if (!log) throw std::runtime_error("failed to flush log: " + path);
}

void write_pid(const std::string& path) {
  std::ofstream file(path, std::ios::trunc);
  if (!file) throw std::runtime_error("cannot write PID file: " + path);
  file << getpid() << '\n';
}

}  // namespace

int main(int argc, char** argv) {
  if (argc != 7) {
    std::cerr << "usage: gpu_reservation TARGET_GIB RESERVE_GIB "
                 "HEARTBEAT_SECONDS EXPECTED_GPU_UUID LOG_JSONL PID_FILE\n";
    return 2;
  }

  void* allocation = nullptr;
  std::string pid_path;
  try {
    const std::uint64_t target_bytes = gib_to_bytes(std::stod(argv[1]));
    const std::uint64_t reserve_bytes = gib_to_bytes(std::stod(argv[2]));
    const int heartbeat_seconds = std::stoi(argv[3]);
    const std::string expected_uuid = argv[4];
    const std::string log_path = argv[5];
    pid_path = argv[6];
    if (heartbeat_seconds <= 0) {
      throw std::invalid_argument("heartbeat seconds must be positive");
    }

    std::signal(SIGINT, handle_signal);
    std::signal(SIGTERM, handle_signal);
    set_process_name();
    check_cuda(cudaSetDevice(0), "cudaSetDevice");
    const std::string uuid = device_uuid();
    if (uuid != expected_uuid) {
      throw std::runtime_error("visible GPU UUID mismatch: expected " +
                               expected_uuid + ", got " + uuid);
    }

    std::size_t free_bytes = 0;
    std::size_t total_bytes = 0;
    check_cuda(cudaMemGetInfo(&free_bytes, &total_bytes), "cudaMemGetInfo");
    if (free_bytes < target_bytes + reserve_bytes) {
      std::ostringstream reason;
      reason << "admission_failed_free=" << free_bytes
             << " required=" << target_bytes + reserve_bytes;
      append_event(log_path, "admission_failed", uuid, 0, free_bytes,
                   total_bytes, reason.str());
      return 3;
    }

    check_cuda(cudaMalloc(&allocation, target_bytes), "cudaMalloc");
    write_pid(pid_path);
    check_cuda(cudaMemGetInfo(&free_bytes, &total_bytes), "cudaMemGetInfo");
    append_event(log_path, "started", uuid, target_bytes, free_bytes,
                 total_bytes);

    while (!stop_requested.load()) {
      for (int elapsed = 0;
           elapsed < heartbeat_seconds && !stop_requested.load(); ++elapsed) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
      }
      if (stop_requested.load()) break;
      check_cuda(cudaMemGetInfo(&free_bytes, &total_bytes), "cudaMemGetInfo");
      append_event(log_path, "heartbeat", uuid, target_bytes, free_bytes,
                   total_bytes);
      if (free_bytes < reserve_bytes) {
        append_event(log_path, "release_requested", uuid, target_bytes,
                     free_bytes, total_bytes, "global_free_below_reserve");
        break;
      }
    }

    check_cuda(cudaFree(allocation), "cudaFree");
    allocation = nullptr;
    check_cuda(cudaMemGetInfo(&free_bytes, &total_bytes), "cudaMemGetInfo");
    append_event(log_path, "stopped", uuid, 0, free_bytes, total_bytes,
                 stop_requested.load() ? "signal" : "release_trigger");
    std::remove(pid_path.c_str());
    return 0;
  } catch (const std::exception& error) {
    if (allocation != nullptr) cudaFree(allocation);
    if (!pid_path.empty()) std::remove(pid_path.c_str());
    std::cerr << "gpu_reservation: " << error.what() << '\n';
    return 1;
  }
}
