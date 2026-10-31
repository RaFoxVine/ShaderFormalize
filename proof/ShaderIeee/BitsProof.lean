import ShaderIeee.GeneratedModel

namespace ShaderIeee.AgentProof

private theorem word_ext (left right : BitVec 32)
    (h : ∀ i : Fin 32, left.getLsbD i.val = right.getLsbD i.val) : left = right := by
  apply BitVec.eq_of_getLsbD_eq
  intro i hi
  exact h ⟨i, hi⟩

theorem equivalent : ShaderIeee.Generated.expected := by
  unfold ShaderIeee.Generated.expected
  intro input
  funext i
  fin_cases i <;>
    dsimp [Generated.original, Generated.optimized] <;>
    simp only [Model.asuint_asfloat] <;>
    congr 1 <;>
    apply UInt32.toBitVec_inj.mp <;>
    simp only [Model.uintAnd, Model.uintOr, Model.uintShiftLeft, Model.uintShiftRight,
      UInt32.toBitVec_and, UInt32.toBitVec_or, UInt32.toBitVec_shiftLeft,
      UInt32.toBitVec_shiftRight] <;>
    apply word_ext <;>
    intro j <;>
    fin_cases j <;>
    simp [BitVec.getLsbD_and, BitVec.getLsbD_or, BitVec.getLsbD_shiftLeft,
      BitVec.getLsbD_ushiftRight, BitVec.getLsbD_ofNat]

end ShaderIeee.AgentProof
