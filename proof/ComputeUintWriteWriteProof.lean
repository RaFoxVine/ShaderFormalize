import ShaderComputeUint.GeneratedModel
namespace ShaderComputeUint.AgentProof
open ShaderComputeUint ShaderComputeUint.Generated
-- Disjoint Source/Output identities remove WR; Count=2 exhibits two in-bounds writers.
private theorem conditions (initial : Memory) (count : UInt32) (hc : inputsValid count) :
    valid threads (original initial count) := by
  have hc2 : count = 2 := by
    apply UInt32.toNat_inj.mp
    simp [inputsValid] at hc
    simp only [UInt32.toNat_ofNat]
    omega
  subst count
  intro t ht a ha he
  have ht32 : t < 2^32 := by simp [threads] at ht; omega
  simp [original] at ha
  rcases ha with rfl | rfl <;>
    simp_all [original,UInt32.lt_iff_toNat_lt] <;> omega

#print axioms conditions

theorem equivalent : expected := by
  classical
  intro initial count hc
  have hv := conditions initial count hc
  have heq : original initial count = optimized initial count := by rfl
  rw [←heq]
  have hi : independent threads (original initial count) := by
    intro t ht u hu hne a ha b hb hea heb hw
    simp [original] at ha hb
    rcases ha with rfl | rfl <;> rcases hb with rfl | rfl <;> simp_all
  exact ⟨⟨hv,hi⟩,⟨hv,hi⟩,rfl⟩
end ShaderComputeUint.AgentProof
