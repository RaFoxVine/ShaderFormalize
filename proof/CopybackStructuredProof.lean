import GeneratedModel
import Mathlib.Tactic.FinCases
import Mathlib.Tactic.Ring

namespace ShaderFormalize.AgentProof

theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops normal view base light rim direction ambient strength
    _baseRange _lightRange _rimRange _ambientRange _strengthRange
    normalNonzero viewNonzero lightNonzero
  dsimp (config := { instances := true }) [Generated.original, Generated.optimized,
    Generated.original_helper0, Generated.original_helper1, Generated.original_helper2,
    Generated.original_helper3, Generated.original_helper4,
    Generated.optimized_helper0, Generated.optimized_helper1,
    Generated.optimized_helper2, Generated.optimized_helper3]
  simp only [ite_true, true_implies, and_true, true_and]
  refine ⟨⟨normalNonzero, viewNonzero, lightNonzero⟩,
    ⟨normalNonzero, lightNonzero, viewNonzero⟩, ?_⟩
  · funext x
    simp only [ShaderFormalize.Control.finish, ShaderFormalize.Fragment.finish,
      List.mem_singleton, forall_eq, ite_true]
    congr 1
    funext i
    fin_cases i <;> dsimp <;> ring

end ShaderFormalize.AgentProof
