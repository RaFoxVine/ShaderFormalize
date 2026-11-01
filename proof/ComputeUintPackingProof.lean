import ShaderComputeUint.GeneratedModel
set_option maxRecDepth 2048
set_option maxHeartbeats 1000000
namespace ShaderComputeUint.AgentProof
open ShaderComputeUint ShaderComputeUint.Generated
private theorem word_ext (left right : BitVec 32)
    (h : ∀ i : Fin 32, left.getLsbD i.val = right.getLsbD i.val) : left = right := by
  apply BitVec.eq_of_getLsbD_eq
  intro i hi
  exact h ⟨i,hi⟩
private theorem extract (a b c d : UInt32) (j : Fin 4) :
    ((((a &&& (255 : UInt32)) ||| ((b &&& (255 : UInt32)) <<< (8 : UInt32)) ||| ((c &&& (255 : UInt32)) <<< (16 : UInt32)) ||| ((d &&& (255 : UInt32)) <<< (24 : UInt32))) >>> (j.val * 8).toUInt32) &&& (255 : UInt32)) =
      ((![a,b,c,d] j) &&& (255 : UInt32)) := by
  fin_cases j <;>
    apply UInt32.toBitVec_inj.mp <;>
    simp only [UInt32.toBitVec_and, UInt32.toBitVec_or, UInt32.toBitVec_shiftLeft,
      UInt32.toBitVec_shiftRight] <;>
    apply word_ext <;>
    intro i <;>
    fin_cases i <;>
    simp [BitVec.getLsbD_and, BitVec.getLsbD_or, BitVec.getLsbD_shiftLeft,
      BitVec.getLsbD_ushiftRight, BitVec.getLsbD_ofNat]

private theorem extract0 (a b c d : UInt32) :
    ((((a &&& (255 : UInt32)) ||| ((b &&& (255 : UInt32)) <<< (8 : UInt32)) ||| ((c &&& (255 : UInt32)) <<< (16 : UInt32)) ||| ((d &&& (255 : UInt32)) <<< (24 : UInt32)))) &&& (255 : UInt32)) = a &&& (255 : UInt32) := by
  simpa using extract a b c d ⟨0, by decide⟩

private theorem extract1 (a b c d : UInt32) :
    ((((a &&& (255 : UInt32)) ||| ((b &&& (255 : UInt32)) <<< (8 : UInt32)) ||| ((c &&& (255 : UInt32)) <<< (16 : UInt32)) ||| ((d &&& (255 : UInt32)) <<< (24 : UInt32))) >>> (8 : UInt32)) &&& (255 : UInt32)) = b &&& (255 : UInt32) := by
  simpa using extract a b c d ⟨1, by decide⟩

private theorem extract2 (a b c d : UInt32) :
    ((((a &&& (255 : UInt32)) ||| ((b &&& (255 : UInt32)) <<< (8 : UInt32)) ||| ((c &&& (255 : UInt32)) <<< (16 : UInt32)) ||| ((d &&& (255 : UInt32)) <<< (24 : UInt32))) >>> (16 : UInt32)) &&& (255 : UInt32)) = c &&& (255 : UInt32) := by
  simpa using extract a b c d ⟨2, by decide⟩

private theorem extract3 (a b c d : UInt32) :
    ((((a &&& (255 : UInt32)) ||| ((b &&& (255 : UInt32)) <<< (8 : UInt32)) ||| ((c &&& (255 : UInt32)) <<< (16 : UInt32)) ||| ((d &&& (255 : UInt32)) <<< (24 : UInt32))) >>> (24 : UInt32)) &&& (255 : UInt32)) = d &&& (255 : UInt32) := by
  simpa using extract a b c d ⟨3, by decide⟩

theorem equivalent : expected := by
  classical
  intro initial count hc
  have hs (kernel : Nat → ThreadResult)
      (h : kernel = original initial count ∨ kernel = optimized initial count) : safe threads kernel := by
    apply safe_of_thread_index
    intro t ht a ha
    have ht32 : t < 2^32 := by simp [threads] at ht; omega
    rcases h with rfl | rfl
    · simp [original] at ha
      rcases ha with rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl <;>
        simp_all [inputsValid, Nat.mod_eq_of_lt ht32]
      all_goals intro he
      all_goals simp_all [UInt32.lt_iff_toNat_lt, UInt32.le_iff_toNat_le, Nat.mod_eq_of_lt ht32]
      all_goals omega
    · simp [optimized] at ha
      rcases ha with rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl <;>
        simp_all [inputsValid, Nat.mod_eq_of_lt ht32]
      all_goals intro he
      all_goals simp_all [UInt32.lt_iff_toNat_lt, UInt32.le_iff_toNat_le, Nat.mod_eq_of_lt ht32]
      all_goals omega
  have ho := hs _ (Or.inl rfl)
  have hp := hs _ (Or.inr rfl)
  refine ⟨ho,hp,?_⟩
  apply finish_eq_of_observations threads initial _ _ ho.2 hp.2
  · intro t ht r i
    simp [touched,original,optimized,or_assoc,or_comm,or_left_comm]
  · intro t ht r i hit
    simp [touched,original] at hit
    simp [original,optimized,store,ShaderIeee.Model.uintAnd,ShaderIeee.Model.uintOr,
      ShaderIeee.Model.uintShiftLeft,ShaderIeee.Model.uintShiftRight]
    split_ifs <;> simp_all [extract0,extract1,extract2,extract3]
end ShaderComputeUint.AgentProof
