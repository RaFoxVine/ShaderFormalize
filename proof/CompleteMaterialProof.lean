import GeneratedModel
import Mathlib.Tactic.FinCases

namespace ShaderFormalize.AgentProof
theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops uv normal view row0 row1 light0 light1 base strength cutoff
    _row0Range _row1Range _light0Range _light1Range _baseRange _strengthRange _cutoffRange
    normalNonzero viewNonzero
  dsimp (config := { instances := true }) [Generated.original, Generated.optimized,
    Generated.original_helper0, Generated.original_helper1,
    Generated.optimized_helper0, Generated.optimized_helper1]
  norm_num [normalNonzero, viewNonzero]
end ShaderFormalize.AgentProof
