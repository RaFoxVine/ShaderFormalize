import ShaderComputeUint.GeneratedModel
namespace ShaderComputeUint.AgentProof
open ShaderComputeUint ShaderComputeUint.Generated
-- Count=2 isolates the neighbor swap: addresses 0/1, injective writes, but WR races.
private theorem conditions (initial : Memory) (count : UInt32) (hc : inputsValid count) :
    valid threads (original initial count) ∧
    (∀ t, t < threads → ∀ u, u < threads → t ≠ u →
      ∀ a ∈ (original initial count t).accesses, ∀ b ∈ (original initial count u).accesses,
      a.enabled → b.enabled → a.write = true → b.write = true → a.address ≠ b.address) := by
  have hc2 : count = 2 := by
    apply UInt32.toNat_inj.mp
    simp [inputsValid] at hc
    simp only [UInt32.toNat_ofNat]
    omega
  subst count
  have enabled_index (t : Nat) (ht : t < threads) (a : Access)
      (ha : a ∈ (original initial 2 t).accesses) (he : a.enabled) : t=0 ∨ t=1 := by
    have ht32 : t < 2^32 := by simp [threads] at ht; omega
    simp [original] at ha
    rcases ha with rfl | rfl <;>
      simp_all [original, UInt32.lt_iff_toNat_lt, Nat.mod_eq_of_lt ht32] <;> omega
  constructor
  · intro t ht a ha he
    have h := enabled_index t ht a ha he
    rcases h with rfl | rfl <;> simp [original] at ha <;> rcases ha with rfl | rfl <;> decide
  · intro t ht u hu hne a ha b hb hea heb hwa hwb
    have ht2 := enabled_index t ht a ha hea
    have hu2 := enabled_index u hu b hb heb
    rcases ht2 with rfl | rfl <;> rcases hu2 with rfl | rfl
    all_goals simp [original] at ha hb
    all_goals rcases ha with rfl | rfl
    all_goals rcases hb with rfl | rfl
    all_goals simp_all
    all_goals decide

#print axioms conditions

theorem equivalent : expected := by
  classical
  intro initial count hc
  obtain ⟨hv,hww⟩ := conditions initial count hc
  have heq : original initial count = optimized initial count := by rfl
  rw [←heq]
  have hi : independent threads (original initial count) := by
    intro t ht u hu hne a ha b hb hea heb hw
    by_cases hwa : a.write = true
    · by_cases hwb : b.write = true
      · exact Or.inr (hww t ht u hu hne a ha b hb hea heb hwa hwb)
      · simp [original] at ha hb
        rcases ha with rfl | rfl <;> rcases hb with rfl | rfl <;> simp_all
    · by_cases hwb : b.write = true
      · simp [original] at ha hb
        rcases ha with rfl | rfl <;> rcases hb with rfl | rfl <;> simp_all
      · exact False.elim (hw.elim hwa hwb)
  exact ⟨⟨hv,hi⟩,⟨hv,hi⟩,rfl⟩
end ShaderComputeUint.AgentProof
