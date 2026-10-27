import GeneratedModel
import Mathlib.Tactic.FinCases

namespace ShaderFormalize.AgentProof
open ShaderFormalize ShaderFormalize.Compute ShaderFormalize.ComputeTexture ShaderFormalize.GeneratedCompute

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
    simp [original, extentX, Nat.mod_eq_of_lt hx32, Nat.mod_eq_of_lt hy32] at ha ⊢
    rcases ha with rfl | rfl | rfl | rfl <;> simp_all <;> omega
  have hpsafe : safe threads (fun t => (optimized initial uniforms t).result) := by
    apply safe_of_pixel_index threads extentX 17 (by omega)
    intro t ht a ha he
    have ht32 : t < 2^32 := by simp only [threads] at ht; omega
    have hx32 : t % 24 < 2^32 := by omega
    have hy32 : t / 24 < 2^32 := by omega
    simp [optimized, extentX, Nat.mod_eq_of_lt hx32, Nat.mod_eq_of_lt hy32] at ha ⊢
    rcases ha with rfl <;> simp_all <;> omega
  have hobligations : ∀ t, t < threads →
      (original initial uniforms t).mathDomains ∧ (original initial uniforms t).storeBounds := by
    intro t ht
    have ht32 : t < 2^32 := by simp only [threads] at ht; omega
    have hx32 : t % 24 < 2^32 := by omega
    have hy32 : t / 24 < 2^32 := by omega
    simp [original, extentX, Nat.mod_eq_of_lt hx32, Nat.mod_eq_of_lt hy32]
    omega
  have hpobligations : ∀ t, t < threads →
      (optimized initial uniforms t).mathDomains ∧ (optimized initial uniforms t).storeBounds := by
    intro t ht
    have ht32 : t < 2^32 := by simp only [threads] at ht; omega
    have hx32 : t % 24 < 2^32 := by omega
    have hy32 : t / 24 < 2^32 := by omega
    simp [optimized, extentX, Nat.mod_eq_of_lt hx32, Nat.mod_eq_of_lt hy32]
    omega
  refine ⟨⟨hobligations, hosafe⟩, ⟨hpobligations, hpsafe⟩, ?_⟩
  apply finish_eq_of_observations threads initial _ _ hosafe.2 hpsafe.2
  · intro t ht r i
    have ht32 : t < 2^32 := by simp only [threads] at ht; omega
    have hx32 : t % 24 < 2^32 := by omega
    have hy32 : t / 24 < 2^32 := by omega
    simp [touched, original, optimized, extentX, Nat.mod_eq_of_lt hx32, Nat.mod_eq_of_lt hy32]
  · intro t ht r i touchedLeft
    have ht32 : t < 2^32 := by simp only [threads] at ht; omega
    have hx32 : t % 24 < 2^32 := by omega
    have hy32 : t / 24 < 2^32 := by omega
    simp [touched, original, extentX, Nat.mod_eq_of_lt hx32, Nat.mod_eq_of_lt hy32] at touchedLeft
    funext c
    simp [original, optimized, store, extentX, Nat.mod_eq_of_lt hx32, Nat.mod_eq_of_lt hy32]
    split_ifs with h
    · fin_cases c <;> rfl
    · rfl

end ShaderFormalize.AgentProof
