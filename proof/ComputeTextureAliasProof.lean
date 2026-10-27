import GeneratedModel

namespace ShaderFormalize.AgentProof
open ShaderFormalize ShaderFormalize.Compute ShaderFormalize.ComputeTexture ShaderFormalize.GeneratedCompute

set_option maxHeartbeats 800000 in
set_option maxRecDepth 4000 in
theorem equivalent : expected := by
  classical
  intro initial uniforms hinputs
  rcases hinputs with ⟨hw0, hw17, hh0, hh13, he0, he4, hb0, hb1⟩
  have hosafe : safe threads (fun t => (original initial uniforms t).result) := by
    apply safe_of_pixel_index threads extentX 17 (by omega)
    intro t ht a ha he
    have ht32 : t < 2^32 := by simp only [threads] at ht; omega
    have hx32 : t % 24 < 2^32 := by omega
    have hy32 : t / 24 < 2^32 := by omega
    have hxint : (BitVec.ofNat 32 (t % 24)).toInt = ((t % 24 : Nat) : Int) := toInt_ofNat32_of_lt (by omega)
    have hyint : (BitVec.ofNat 32 (t / 24)).toInt = ((t / 24 : Nat) : Int) := toInt_ofNat32_of_lt (by omega)
    have hxnat : (BitVec.ofNat 32 (t % 24)).toInt.toNat = t % 24 := toNat_toInt_ofNat32_of_lt (by omega)
    have hynat : (BitVec.ofNat 32 (t / 24)).toInt.toNat = t / 24 := toNat_toInt_ofNat32_of_lt (by omega)
    simp [original, extentX, Nat.mod_eq_of_lt hx32, Nat.mod_eq_of_lt hy32, hxint, hyint, hxnat, hynat] at ha ⊢
    rcases ha with rfl | rfl | rfl | rfl | rfl | rfl <;> simp [extentX] at he <;> simp_all <;> omega
  have hpsafe : safe threads (fun t => (optimized initial uniforms t).result) := by
    apply safe_of_pixel_index threads extentX 17 (by omega)
    intro t ht a ha he
    have ht32 : t < 2^32 := by simp only [threads] at ht; omega
    have hx32 : t % 24 < 2^32 := by omega
    have hy32 : t / 24 < 2^32 := by omega
    have hxint : (BitVec.ofNat 32 (t % 24)).toInt = ((t % 24 : Nat) : Int) := toInt_ofNat32_of_lt (by omega)
    have hyint : (BitVec.ofNat 32 (t / 24)).toInt = ((t / 24 : Nat) : Int) := toInt_ofNat32_of_lt (by omega)
    have hxnat : (BitVec.ofNat 32 (t % 24)).toInt.toNat = t % 24 := toNat_toInt_ofNat32_of_lt (by omega)
    have hynat : (BitVec.ofNat 32 (t / 24)).toInt.toNat = t / 24 := toNat_toInt_ofNat32_of_lt (by omega)
    simp [optimized, extentX, Nat.mod_eq_of_lt hx32, Nat.mod_eq_of_lt hy32, hxint, hyint, hxnat, hynat] at ha ⊢
    rcases ha with rfl | rfl | rfl <;> simp [extentX] at he <;> simp_all <;> omega
  have hobligations : ∀ t, t < threads →
      (original initial uniforms t).mathDomains ∧ (original initial uniforms t).storeBounds := by
    intro t ht
    have ht32 : t < 2^32 := by simp only [threads] at ht; omega
    have hx32 : t % 24 < 2^32 := by omega
    have hy32 : t / 24 < 2^32 := by omega
    have hxint : (BitVec.ofNat 32 (t % 24)).toInt = ((t % 24 : Nat) : Int) := toInt_ofNat32_of_lt (by omega)
    have hyint : (BitVec.ofNat 32 (t / 24)).toInt = ((t / 24 : Nat) : Int) := toInt_ofNat32_of_lt (by omega)
    have hxnat : (BitVec.ofNat 32 (t % 24)).toInt.toNat = t % 24 := toNat_toInt_ofNat32_of_lt (by omega)
    have hynat : (BitVec.ofNat 32 (t / 24)).toInt.toNat = t / 24 := toNat_toInt_ofNat32_of_lt (by omega)
    simp [original, extentX, Nat.mod_eq_of_lt hx32, Nat.mod_eq_of_lt hy32, hxint, hyint, hxnat, hynat]
    omega
  have hpobligations : ∀ t, t < threads →
      (optimized initial uniforms t).mathDomains ∧ (optimized initial uniforms t).storeBounds := by
    intro t ht
    have ht32 : t < 2^32 := by simp only [threads] at ht; omega
    have hx32 : t % 24 < 2^32 := by omega
    have hy32 : t / 24 < 2^32 := by omega
    have hxint : (BitVec.ofNat 32 (t % 24)).toInt = ((t % 24 : Nat) : Int) := toInt_ofNat32_of_lt (by omega)
    have hyint : (BitVec.ofNat 32 (t / 24)).toInt = ((t / 24 : Nat) : Int) := toInt_ofNat32_of_lt (by omega)
    have hxnat : (BitVec.ofNat 32 (t % 24)).toInt.toNat = t % 24 := toNat_toInt_ofNat32_of_lt (by omega)
    have hynat : (BitVec.ofNat 32 (t / 24)).toInt.toNat = t / 24 := toNat_toInt_ofNat32_of_lt (by omega)
    simp [optimized, extentX, Nat.mod_eq_of_lt hx32, Nat.mod_eq_of_lt hy32, hxint, hyint, hxnat, hynat]
    omega
  refine ⟨⟨hobligations, hosafe⟩, ⟨hpobligations, hpsafe⟩, ?_⟩
  apply finish_eq_of_observations threads initial _ _ hosafe.2 hpsafe.2
  · intro t ht r i
    have ht32 : t < 2^32 := by simp only [threads] at ht; omega
    have hx32 : t % 24 < 2^32 := by omega
    have hy32 : t / 24 < 2^32 := by omega
    have hxint : (BitVec.ofNat 32 (t % 24)).toInt = ((t % 24 : Nat) : Int) := toInt_ofNat32_of_lt (by omega)
    have hyint : (BitVec.ofNat 32 (t / 24)).toInt = ((t / 24 : Nat) : Int) := toInt_ofNat32_of_lt (by omega)
    have hxnat : (BitVec.ofNat 32 (t % 24)).toInt.toNat = t % 24 := toNat_toInt_ofNat32_of_lt (by omega)
    have hynat : (BitVec.ofNat 32 (t / 24)).toInt.toNat = t / 24 := toNat_toInt_ofNat32_of_lt (by omega)
    simp [touched, original, optimized, extentX, Nat.mod_eq_of_lt hx32, Nat.mod_eq_of_lt hy32,
      or_left_comm, or_comm, or_assoc]
  · intro t ht r i touchedLeft
    have ht32 : t < 2^32 := by simp only [threads] at ht; omega
    have hx32 : t % 24 < 2^32 := by omega
    have hy32 : t / 24 < 2^32 := by omega
    have hxnat : (BitVec.ofNat 32 (t % 24)).toInt.toNat = t % 24 := toNat_toInt_ofNat32_of_lt (by omega)
    have hynat : (BitVec.ofNat 32 (t / 24)).toInt.toNat = t / 24 := toNat_toInt_ofNat32_of_lt (by omega)
    have address_same : t / 24 * 17 + t % 24 = t / 24 % 2^32 * 17 + t % 24 % 2^32 := by
      rw [Nat.mod_eq_of_lt hx32, Nat.mod_eq_of_lt hy32]
    simp [touched, original, extentX, Nat.mod_eq_of_lt hx32, Nat.mod_eq_of_lt hy32, hxnat, hynat] at touchedLeft
    rcases touchedLeft with h | h
    · rcases h with ⟨⟨active, bounds⟩, hr, hi⟩
      have hxint : (BitVec.ofNat 32 (t % 24)).toInt = ((t % 24 : Nat) : Int) := toInt_ofNat32_of_lt (by omega)
      have hyint : (BitVec.ofNat 32 (t / 24)).toInt = ((t / 24 : Nat) : Int) := toInt_ofNat32_of_lt (by omega)
      have load_bounds : 0 ≤ (BitVec.ofNat 32 (t % 24)).toInt ∧ (BitVec.ofNat 32 (t % 24)).toInt < 17 ∧
          0 ≤ (BitVec.ofNat 32 (t / 24)).toInt ∧ (BitVec.ofNat 32 (t / 24)).toInt < 13 := by
        rw [hxint, hyint]
        norm_cast
        omega
      subst r
      subst i
      funext c
      simp [original, optimized, store, extentX, active, bounds, hxnat, hynat, address_same, load_bounds] <;> ring
    · rcases h with ⟨⟨active, bounds⟩, hr, hi⟩
      have hxint : (BitVec.ofNat 32 (t % 24)).toInt = ((t % 24 : Nat) : Int) := toInt_ofNat32_of_lt (by omega)
      have hyint : (BitVec.ofNat 32 (t / 24)).toInt = ((t / 24 : Nat) : Int) := toInt_ofNat32_of_lt (by omega)
      have load_bounds : 0 ≤ (BitVec.ofNat 32 (t % 24)).toInt ∧ (BitVec.ofNat 32 (t % 24)).toInt < 17 ∧
          0 ≤ (BitVec.ofNat 32 (t / 24)).toInt ∧ (BitVec.ofNat 32 (t / 24)).toInt < 13 := by
        rw [hxint, hyint]
        norm_cast
        omega
      subst r
      subst i
      funext c
      simp [original, optimized, store, extentX, active, bounds, hxnat, hynat, address_same, load_bounds] <;> ring

end ShaderFormalize.AgentProof
