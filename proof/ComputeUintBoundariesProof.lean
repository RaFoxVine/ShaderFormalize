import ShaderComputeUint.GeneratedModel
namespace ShaderComputeUint.AgentProof
open ShaderComputeUint ShaderComputeUint.Generated
private theorem sl32 (x : UInt32) : x <<< (32 : UInt32) = x <<< (0 : UInt32) := by
  simpa using UInt32.shiftLeft_eq_shiftLeft_mod x 32
private theorem sl33 (x : UInt32) : x <<< (33 : UInt32) = x <<< (1 : UInt32) := by
  simpa using UInt32.shiftLeft_eq_shiftLeft_mod x 33
private theorem slmax (x : UInt32) : x <<< (4294967295 : UInt32) = x <<< (31 : UInt32) := by
  simpa using UInt32.shiftLeft_eq_shiftLeft_mod x 4294967295
private theorem sr32 (x : UInt32) : x >>> (32 : UInt32) = x >>> (0 : UInt32) := by
  simpa using UInt32.shiftRight_eq_shiftRight_mod x 32
private theorem sr33 (x : UInt32) : x >>> (33 : UInt32) = x >>> (1 : UInt32) := by
  simpa using UInt32.shiftRight_eq_shiftRight_mod x 33
private theorem srmax (x : UInt32) : x >>> (4294967295 : UInt32) = x >>> (31 : UInt32) := by
  simpa using UInt32.shiftRight_eq_shiftRight_mod x 4294967295

theorem equivalent : expected := by
  classical
  intro initial count hc
  have addr0 : ShaderIeee.Model.uintAdd (ShaderIeee.Model.uintAdd 0 4294967295) 1 = 0 := by decide
  have addrmax : ShaderIeee.Model.uintSubtract 0 1 = 4294967295 := by decide
  have heq : original initial count = optimized initial count := by
    funext t
    simp [original,optimized,addr0,addrmax,ShaderIeee.Model.uintShiftLeft,
      ShaderIeee.Model.uintShiftRight,sl32,sl33,slmax,sr32,sr33,srmax]
  have hs : safe threads (original initial count) := by
    constructor
    · intro t ht a ha he
      simp [original] at ha
      rcases ha with rfl | rfl | rfl | rfl <;>
        simp_all [inputsValid,UInt32.lt_iff_toNat_lt] <;> omega
    · intro t ht u hu hne a ha b hb hea heb hw
      have ht32 : t < 2^32 := by simp [threads] at ht; omega
      have hu32 : u < 2^32 := by simp [threads] at hu; omega
      simp [original] at ha hb
      rcases ha with rfl | rfl | rfl | rfl <;>
        rcases hb with rfl | rfl | rfl | rfl <;>
        simp_all [Nat.mod_eq_of_lt ht32,Nat.mod_eq_of_lt hu32]
      all_goals have htm : t % 4294967296 = t := Nat.mod_eq_of_lt ht32
      all_goals have hum : u % 4294967296 = u := Nat.mod_eq_of_lt hu32
      all_goals omega
  rw [←heq]
  exact ⟨hs,hs,rfl⟩
end ShaderComputeUint.AgentProof
