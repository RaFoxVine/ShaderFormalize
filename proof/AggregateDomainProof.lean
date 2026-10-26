import GeneratedModel
namespace ShaderFormalize.AgentProof
theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops a range
  have zero : a = fun _ _ => 0 := by
    funext x i
    exact le_antisymm (range x i).2 (range x i).1
  have index0 : (0 : BitVec 32).toNat = 0 := rfl
  have index1 : (1 : BitVec 32).toNat = 1 := rfl
  have index2 : (2 : BitVec 32).toNat = 2 := rfl
  dsimp [Generated.original, Generated.optimized, Generated.original_helper0]
  try simp only [zero, index0, index1, index2]
  norm_num [ShaderFormalize.Control.finish, ShaderFormalize.Fragment.finish]
end ShaderFormalize.AgentProof
