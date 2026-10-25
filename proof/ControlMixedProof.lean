import GeneratedModel

namespace ShaderFormalize.AgentProof
theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops a h
  have ha : a = fun _ _ => (0 : ℝ) := by
    funext x i
    exact le_antisymm (h x i).2 (h x i).1
  subst a
  norm_num [Generated.original, Generated.optimized, ShaderFormalize.Control.finish,
    ShaderFormalize.Fragment.finish]
  funext x
  simp [ShaderFormalize.Fragment.finish]
end ShaderFormalize.AgentProof
