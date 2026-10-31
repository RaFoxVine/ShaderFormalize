import ShaderIeee.GeneratedModel

namespace ShaderIeee.AgentProof

-- Closed boundary cases are checked by kernel reduction, without native_decide.
example : Model.uintShiftLeft 1 0 = 1 := by decide
example : Model.uintShiftLeft 1 31 = 0x80000000 := by decide
example : Model.uintShiftLeft 1 32 = 1 := by decide
example : Model.uintShiftLeft 1 33 = 2 := by decide
example : Model.uintShiftLeft 1 0xFFFFFFFF = 0x80000000 := by decide
example : Model.uintShiftRight 0x80000000 31 = 1 := by decide
example : Model.uintShiftRight 0x80000000 32 = 0x80000000 := by decide
example : Model.uintShiftRight 0x80000000 33 = 0x40000000 := by decide
example : Model.uintShiftRight 0x80000000 0xFFFFFFFF = 1 := by decide
example : Model.uintAdd 0xFFFFFFFF 1 = 0 := by decide
example : Model.uintMultiply 0xFFFFFFFF 2 = 0xFFFFFFFE := by decide
example : (0x80000000 : UInt32) > 1 := by decide
example : ¬ ((0xFFFFFFFF : UInt32) < 0x80000000) := by decide

theorem equivalent : ShaderIeee.Generated.expected := by
  unfold ShaderIeee.Generated.expected
  intro input
  funext i
  fin_cases i <;>
    dsimp [Generated.original, Generated.optimized] <;>
    apply congrArg Model.asfloat
  · simp [Model.uintAdd, UInt32.add_assoc]
  · apply UInt32.toBitVec_inj.mp
    simp [Model.uintNegate]
  · apply UInt32.toBitVec_inj.mp
    simp [Model.uintNot, BitVec.not_not]
  · simp [Model.uintXor, UInt32.xor_assoc]

end ShaderIeee.AgentProof
