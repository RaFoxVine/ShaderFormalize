import GeneratedModel
import Mathlib.Tactic.FinCases
import Mathlib.Tactic.Ring

namespace ShaderFormalize.AgentProof

theorem equivalent : ShaderFormalize.Generated.expected := by
  intro E ops uv tint transform cutoff bottom mip strength
    _tintRange _cutoffRange _bottomRange _mipRange _strengthRange
  dsimp [Generated.original, Generated.optimized]
  congr 1
  funext x i
  fin_cases i <;> dsimp <;> ring

end ShaderFormalize.AgentProof
