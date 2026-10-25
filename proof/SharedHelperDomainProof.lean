import GeneratedModel
namespace ShaderFormalize.AgentProof

theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops a range
  have zero : a = fun _ _ => 0 := by
    funext x i
    exact le_antisymm (range x i).2 (range x i).1
  norm_num [Generated.original, Generated.optimized, Generated.original_helper0,
    zero, ShaderFormalize.Control.finish, ShaderFormalize.Fragment.finish]

end ShaderFormalize.AgentProof
