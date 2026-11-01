import ShaderFormalize.Model
import ShaderFormalize.ComputeMemory
namespace ShaderFormalize.Compute
abbrev Color := Model.Vec4
abbrev Memory := ComputeMemory.Memory Color
abbrev ThreadResult := ComputeMemory.ThreadResult Color
export ComputeMemory (Access store touched finish valid independent safe
  safe_of_thread_index finish_congr finish_eq_of_observations)
end ShaderFormalize.Compute
