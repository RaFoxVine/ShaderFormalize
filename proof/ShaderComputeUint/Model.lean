import ShaderFormalize.ComputeMemory
import ShaderIeee.Model
namespace ShaderComputeUint
abbrev Memory := ShaderFormalize.ComputeMemory.Memory UInt32
abbrev ThreadResult := ShaderFormalize.ComputeMemory.ThreadResult UInt32
export ShaderFormalize.ComputeMemory (Access store touched finish valid independent safe
  safe_of_thread_index finish_congr finish_eq_of_observations)
end ShaderComputeUint
