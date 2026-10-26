import GeneratedModel
import Mathlib.Tactic.FinCases
import Mathlib.Tactic.Ring

namespace ShaderFormalize.AgentProof
theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops normal view row0 row1 light0 light1 base strength
    _row0Range _row1Range _light0Range _light1Range _baseRange _strengthRange
    normalNonzero viewNonzero
  dsimp [Generated.original, Generated.optimized,
    Generated.original_helper0, Generated.original_helper1, Generated.original_helper2]
  simp only [if_true, true_implies, and_true, true_and]
  refine ⟨?_, ?_, ?_⟩
  · norm_num [normalNonzero, viewNonzero]
  · norm_num [normalNonzero, viewNonzero]
  · funext x
    simp only [ShaderFormalize.Control.finish, ShaderFormalize.Fragment.finish,
      List.mem_singleton, forall_eq, if_true]
    congr 1
    funext i
    fin_cases i <;> dsimp <;> ring
end ShaderFormalize.AgentProof
