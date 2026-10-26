import ShaderFormalize.Model

namespace ShaderFormalize.Compute

abbrev Color := Model.Vec4
abbrev Memory := Nat → Nat → Color

structure Access where
  resource : Nat
  address : Nat
  capacity : Nat
  enabled : Prop
  write : Bool

structure ThreadResult where
  memory : Memory
  accesses : List Access

noncomputable def store (memory : Memory) (enabled : Prop) (resource address : Nat)
    (value : Color) : Memory := by
  classical
  exact fun r i => if enabled ∧ r = resource ∧ i = address then value else memory r i

def touched (result : ThreadResult) (resource address : Nat) : Prop :=
  ∃ access ∈ result.accesses, access.enabled ∧ access.write = true ∧
    access.resource = resource ∧ access.address = address

-- This is a unique-writer semantics, not a selected GPU thread schedule.
-- Safety below proves that all possible writers of a location are the same
-- thread; its final memory includes all its ordered, guarded stores.
noncomputable def finish (threads : Nat) (initial : Memory)
    (kernel : Nat → ThreadResult) : Memory := by
  classical
  exact fun resource address =>
    if h : ∃ thread, thread < threads ∧ touched (kernel thread) resource address then
      (kernel (Classical.choose h)).memory resource address
    else initial resource address

def valid (threads : Nat) (kernel : Nat → ThreadResult) : Prop :=
  ∀ thread, thread < threads → ∀ access ∈ (kernel thread).accesses,
    access.enabled → access.address < access.capacity

def independent (threads : Nat) (kernel : Nat → ThreadResult) : Prop :=
  ∀ t, t < threads → ∀ u, u < threads → t ≠ u →
    ∀ a ∈ (kernel t).accesses, ∀ b ∈ (kernel u).accesses,
    a.enabled → b.enabled → (a.write = true ∨ b.write = true) →
    a.resource ≠ b.resource ∨ a.address ≠ b.address

def safe (threads : Nat) (kernel : Nat → ThreadResult) : Prop :=
  valid threads kernel ∧ independent threads kernel

theorem safe_of_thread_index (threads : Nat) (kernel : Nat → ThreadResult)
    (h : ∀ t, t < threads → ∀ a ∈ (kernel t).accesses,
      a.address = t ∧ (a.enabled → t < a.capacity)) : safe threads kernel := by
  constructor
  · intro t ht a ha he
    obtain ⟨haddr, hbound⟩ := h t ht a ha
    rw [haddr]
    exact hbound he
  · intro t ht u hu hne a ha b hb _ _ _
    right
    rw [(h t ht a ha).1, (h u hu b hb).1]
    exact hne

theorem finish_congr (threads : Nat) (initial : Memory) (left right : Nat → ThreadResult)
    (h : left = right) : finish threads initial left = finish threads initial right := by
  rw [h]

theorem finish_eq_of_observations (threads : Nat) (initial : Memory)
    (left right : Nat → ThreadResult)
    (hl : independent threads left) (hr : independent threads right)
    (ht : ∀ t, t < threads → ∀ r i, touched (left t) r i ↔ touched (right t) r i)
    (hm : ∀ t, t < threads → ∀ r i, touched (left t) r i →
      (left t).memory r i = (right t).memory r i) :
    finish threads initial left = finish threads initial right := by
  classical
  funext r i
  unfold finish
  split_ifs with hleft hright hright
  · let t := Classical.choose hleft
    let u := Classical.choose hright
    obtain ⟨htb, hat⟩ := Classical.choose_spec hleft
    obtain ⟨hub, hbu⟩ := Classical.choose_spec hright
    have hsame : t = u := by
      by_contra hne
      obtain ⟨a, ha, hea, hwa, hra, hia⟩ := hat
      obtain ⟨b, hb, heb, hwb, hrb, hib⟩ := (ht u hub r i).mpr hbu
      rcases hl t htb u hub hne a ha b hb hea heb (Or.inl hwa) with h | h
      · exact h (hra.trans hrb.symm)
      · exact h (hia.trans hib.symm)
    have hmem := hm t htb r i hat
    simpa [t, u, hsame] using hmem
  · exfalso
    obtain ⟨t, htb, htouched⟩ := hleft
    exact hright ⟨t, htb, (ht t htb r i).mp htouched⟩
  · exfalso
    obtain ⟨t, htb, htouched⟩ := hright
    exact hleft ⟨t, htb, (ht t htb r i).mpr htouched⟩
  · rfl

end ShaderFormalize.Compute
