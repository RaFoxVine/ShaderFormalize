import GeneratedModel

namespace ShaderFormalize.AgentProof
open ShaderFormalize ShaderFormalize.Compute ShaderFormalize.GeneratedCompute

theorem equivalent : expected := by
  classical
  intro initial count hcount
  rcases hcount with ⟨hlo, hhi⟩
  have hosafe : safe threads (original initial count) := by
    apply safe_of_thread_index
    intro t ht a ha
    have ht32 : t < 2^32 := by simp only [threads] at ht; omega
    simp [original, Nat.mod_eq_of_lt ht32] at ha
    rcases ha with rfl | rfl | rfl | rfl <;> simp_all [not_le] <;> omega
  have hpsafe : safe threads (optimized initial count) := by
    apply safe_of_thread_index
    intro t ht a ha
    have ht32 : t < 2^32 := by simp only [threads] at ht; omega
    simp [optimized, Nat.mod_eq_of_lt ht32] at ha
    rcases ha with rfl | rfl | rfl | rfl <;> simp_all [not_le] <;> omega
  refine ⟨hosafe, hpsafe, ?_⟩
  apply finish_eq_of_observations threads initial _ _ hosafe.2 hpsafe.2
  · intro t ht r i
    simp [touched, original, optimized, not_le, or_left_comm, or_comm, or_assoc]
  · intro t ht r i touchedLeft
    simp [touched, original, not_le] at touchedLeft
    funext c
    simp only [original, optimized, Id.run, pure, BitVec.add_zero, store]
    split_ifs <;> simp_all [not_le]
    all_goals first | omega | ring

end ShaderFormalize.AgentProof
