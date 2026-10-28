import GeneratedModel
import Mathlib.Tactic.FinCases
import Mathlib.Tactic.Ring

namespace ShaderFormalize.AgentProof
theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops a
  dsimp [Generated.original, Generated.optimized]
  simp only [ite_true, true_implies, and_true, true_and]
  funext x
  simp only [ShaderFormalize.Control.finish, ShaderFormalize.Fragment.finish,
    List.mem_singleton, forall_eq, ite_true]
  congr 1
  funext i
  fin_cases i <;> dsimp
  · exact Int.floor_add_fract _
  · simp [Int.floor_neg]
end ShaderFormalize.AgentProof
