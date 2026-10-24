import GeneratedModel
import Mathlib.Tactic.FinCases
import Mathlib.Tactic.Ring

namespace ShaderFormalize.AgentProof

theorem equivalent : ShaderFormalize.Generated.expected := by
  intro normal view base light rim direction ambient strength
    _baseRange _lightRange _rimRange _ambientLo _ambientHi _strengthLo _strengthHi
    _normalNonzero _viewNonzero _lightNonzero
  funext i
  fin_cases i <;> dsimp [Generated.original, Generated.optimized] <;> ring

end ShaderFormalize.AgentProof
