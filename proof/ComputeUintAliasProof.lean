import ShaderComputeUint.GeneratedModel
namespace ShaderComputeUint.AgentProof
open ShaderComputeUint ShaderComputeUint.Generated
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
      rcases ha with rfl | rfl | rfl | rfl <;> simp_all [inputsValid]
      all_goals intro he
      all_goals simp_all [UInt32.lt_iff_toNat_lt,Nat.mod_eq_of_lt ht32]
      all_goals omega
    · simp [optimized] at ha
      rcases ha with rfl | rfl <;> simp_all [inputsValid]
      all_goals intro he
      all_goals simp_all [UInt32.lt_iff_toNat_lt,Nat.mod_eq_of_lt ht32]
      all_goals omega
  have ho := hs _ (Or.inl rfl)
  have hp := hs _ (Or.inr rfl)
  refine ⟨ho,hp,?_⟩
  apply finish_eq_of_observations threads initial _ _ ho.2 hp.2
  · intro t ht r i
    simp [touched,original,optimized,or_assoc,or_comm,or_left_comm]
  · intro t ht r i hit
    simp [touched,original] at hit
    simp [original,optimized,store]
    split_ifs <;> simp_all
end ShaderComputeUint.AgentProof
