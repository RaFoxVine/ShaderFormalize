import GeneratedModel

namespace ShaderFormalize.AgentProof
theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops a
  refine ⟨?_, ?_, ?_⟩
  · simp [Generated.original]
  · simp [Generated.optimized]
  · funext x
    by_cases h : (0 : ℝ) < ShaderFormalize.Model.dot
      (fun i : Fin 3 => a x ⟨i.val, by omega⟩)
      (fun i : Fin 3 => a x ⟨i.val, by omega⟩)
    all_goals simp_all [Generated.original, Generated.optimized, ShaderFormalize.Control.finish,
      ShaderFormalize.Fragment.finish]
end ShaderFormalize.AgentProof
