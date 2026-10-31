import ShaderIeee.GeneratedModel

namespace ShaderIeee.AgentProof

private theorem mask_count (count : UInt32) : count &&& 31 = count % 32 := by
  apply UInt32.toNat_inj.mp
  simpa using Nat.and_two_pow_sub_one_eq_mod count.toNat 5

theorem equivalent : ShaderIeee.Generated.expected := by
  unfold ShaderIeee.Generated.expected
  intro input
  funext i
  fin_cases i <;>
    dsimp [Generated.original, Generated.optimized] <;>
    congr 1 <;>
    dsimp [Model.uintShiftLeft, Model.uintShiftRight, Model.uintAnd] <;>
    rw [mask_count]
  · exact UInt32.shiftLeft_eq_shiftLeft_mod _ _
  · exact UInt32.shiftRight_eq_shiftRight_mod _ _

end ShaderIeee.AgentProof
