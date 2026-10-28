import GeneratedModel
import Mathlib.Tactic.FinCases

namespace ShaderFormalize.AgentProof
theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops a
  refine ⟨?_, ?_, ?_⟩
  · exact True.intro
  · exact True.intro
  · funext x
    dsimp [Generated.original, Generated.optimized]
    simp only [ShaderFormalize.Control.finish, ShaderFormalize.Fragment.finish,
      List.mem_singleton, forall_eq, ite_true]
    congr 1
    funext i
    fin_cases i <;> rfl
end ShaderFormalize.AgentProof
