import ShaderComputeUint.GeneratedModel
namespace ShaderComputeUint.AgentProof
open ShaderComputeUint ShaderComputeUint.Generated
private theorem wrap (x : UInt32) : ShaderIeee.Model.uintAdd (ShaderIeee.Model.uintAdd x 4294967295) 1 = x := by
  simp [ShaderIeee.Model.uintAdd, UInt32.add_assoc]
theorem equivalent : expected := by
  classical
  intro initial count hc
  have heq : original initial count = optimized initial count := by
    funext t
    simp [original, optimized, wrap]
  have hs : safe threads (optimized initial count) := by
    apply safe_of_thread_index
    intro t ht a ha
    have ht32 : t < 2^32 := by simp [threads] at ht; omega
    simp [optimized] at ha
    rcases ha with rfl | rfl <;>
      simp_all [inputsValid, UInt32.toNat_ofNat, Nat.mod_eq_of_lt ht32]
    all_goals intro he
    all_goals simp_all [UInt32.lt_iff_toNat_lt, UInt32.le_iff_toNat_le, Nat.mod_eq_of_lt ht32]
    all_goals omega
  rw [heq]
  exact ⟨hs, hs, rfl⟩
end ShaderComputeUint.AgentProof
