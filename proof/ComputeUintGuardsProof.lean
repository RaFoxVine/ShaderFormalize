import ShaderComputeUint.GeneratedModel
namespace ShaderComputeUint.AgentProof
open ShaderComputeUint ShaderComputeUint.Generated
 theorem equivalent : expected := by
  classical
  intro initial count hc
  have hs : safe threads (original initial count) := by
    apply safe_of_thread_index
    intro t ht a ha
    have ht32 : t < 2^32 := by simp [threads] at ht; omega
    simp [original] at ha
    rcases ha with rfl | rfl | rfl | rfl | rfl <;>
      simp_all [inputsValid, Nat.mod_eq_of_lt ht32]
    all_goals intro he
    all_goals simp_all [UInt32.lt_iff_toNat_lt, UInt32.le_iff_toNat_le, Nat.mod_eq_of_lt ht32]
    all_goals omega
  have eq : original = optimized := by rfl
  rw [←eq]
  exact ⟨hs,hs,rfl⟩
end ShaderComputeUint.AgentProof
