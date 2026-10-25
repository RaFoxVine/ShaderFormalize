import GeneratedModel

namespace ShaderFormalize.AgentProof
theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops a
  refine ⟨True.intro, True.intro, ?_⟩
  funext x
  by_cases hx : (a x ⟨0, by decide⟩) > (1/2 : ℝ)
  all_goals by_cases hy : (a x ⟨1, by decide⟩) > (1/2 : ℝ)
  all_goals simp_all [Generated.original, Generated.optimized, ShaderFormalize.Control.finish,
    ShaderFormalize.Fragment.finish]
end ShaderFormalize.AgentProof
