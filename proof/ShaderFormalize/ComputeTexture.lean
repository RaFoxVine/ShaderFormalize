import ShaderFormalize.Compute

namespace ShaderFormalize.ComputeTexture
open ShaderFormalize.Compute

/-- A texture-thread execution retains source-level safety obligations even when
    the total memory model masks an invalid access. -/
structure Execution where
  result : ThreadResult
  mathDomains : Prop
  storeBounds : Prop

def allValid (threads : Nat) (kernel : Nat → Execution) : Prop :=
  (∀ thread, thread < threads →
    (kernel thread).mathDomains ∧ (kernel thread).storeBounds) ∧
  safe threads (fun thread => (kernel thread).result)

theorem toInt_ofNat32_of_lt {x : Nat} (h : x < 2^31) :
    (BitVec.ofNat 32 x).toInt = (x : Int) := by
  rw [BitVec.toInt_ofNat', Int.bmod_eq_of_le] <;> push_cast <;> omega

theorem toNat_toInt_ofNat32_of_lt {x : Nat} (h : x < 2^31) :
    (BitVec.ofNat 32 x).toInt.toNat = x := by
  rw [toInt_ofNat32_of_lt h]
  simp

theorem rowMajor_injective {width x y x' y' : Nat}
    (hw : 0 < width) (hx : x < width) (hx' : x' < width)
    (h : y * width + x = y' * width + x') : x = x' ∧ y = y' := by
  have hmod := congrArg (fun n => n % width) h
  have hxx : x = x' := by simpa [Nat.add_mod, Nat.mod_eq_of_lt hx, Nat.mod_eq_of_lt hx'] using hmod
  refine ⟨hxx, ?_⟩
  have hm : y * width = y' * width := by omega
  exact Nat.eq_of_mul_eq_mul_right hw hm

/-- Every actual access has its dispatch pixel's address. This permits arbitrary
    guarded missing pixels, view aliases and multiple ordered accesses. -/
theorem safe_of_pixel_index (threads pitch width : Nat) (hw : 0 < width)
    (kernel : Nat → ThreadResult)
    (h : ∀ t, t < threads → ∀ a ∈ (kernel t).accesses, a.enabled →
      a.address = (t / pitch) * width + t % pitch ∧
      t % pitch < width ∧ a.address < a.capacity) : safe threads kernel := by
  constructor
  · intro t ht a ha he
    exact (h t ht a ha he).2.2
  · intro t ht u hu hne a ha b hb hea heb _
    right
    intro heq
    obtain ⟨hat, htx, _⟩ := h t ht a ha hea
    obtain ⟨hbu, hux, _⟩ := h u hu b hb heb
    have hp := rowMajor_injective hw htx hux (hat.symm.trans (heq.trans hbu))
    have htdecomp := Nat.mod_add_div t pitch
    have hudecomp := Nat.mod_add_div u pitch
    apply hne
    rw [hp.1, hp.2] at htdecomp
    omega

end ShaderFormalize.ComputeTexture
