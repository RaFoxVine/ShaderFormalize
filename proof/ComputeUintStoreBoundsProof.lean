import ShaderComputeUint.GeneratedModel
namespace ShaderComputeUint.AgentProof
open ShaderComputeUint ShaderComputeUint.Generated
private theorem conditions (initial : Memory) (count : UInt32) (hc : inputsValid count) :
    (∀ t, t < threads → ∀ a ∈ (original initial count t).accesses,
      a.enabled → a.write = false → a.address < a.capacity) ∧
    independent threads (original initial count) ∧
    original initial count = optimized initial count := by
  have hc1 : count = 1 := by
    apply UInt32.toNat_inj.mp
    simp [inputsValid] at hc
    simp only [UInt32.toNat_ofNat]
    omega
  subst count
  refine ⟨?_,?_,by rfl⟩
  · intro t ht a ha he hw
    have ht0 : t=0 := by simp [threads] at ht; omega
    subst t
    simp [original] at ha
    rcases ha with rfl | rfl <;> simp_all [original]
  · intro t ht u hu hne
    have ht0 : t=0 := by simp [threads] at ht; omega
    have hu0 : u=0 := by simp [threads] at hu; omega
    exact False.elim (hne (ht0.trans hu0.symm))
#print axioms conditions

theorem equivalent : expected := by
  classical
  intro initial count hc
  obtain ⟨otherBounds,hi,heq⟩ := conditions initial count hc
  have hc1 : count = 1 := by
    apply UInt32.toNat_inj.mp
    simp [inputsValid] at hc
    simp only [UInt32.toNat_ofNat]
    omega
  subst count
  rw [←heq]
  have hv : valid threads (original initial 1) := by
    intro t ht a ha he
    have ht0 : t=0 := by simp [threads] at ht; omega
    subst t
    simp [original] at ha
    rcases ha with rfl | rfl
    · change (0 : Nat) < 113
      decide
    · change (113 : Nat) < 113
      trace_state
      omega

  exact ⟨⟨hv,hi⟩,⟨hv,hi⟩,rfl⟩
end ShaderComputeUint.AgentProof
