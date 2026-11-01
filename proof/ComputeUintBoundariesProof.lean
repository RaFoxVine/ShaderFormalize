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

-- The reference functions are standard UInt32 expressions, not another HLSL interpreter.
-- reference_binding below binds both outputs to the actual generated original kernel.
private def inputMemory (x y : UInt32) : Memory := fun r i =>
  if r = 0 then (if i = 0 then x else if i = 4294967295 then y else 0) else 0
private def leftReference (x y : UInt32) : UInt32 :=
  ((x <<< (0 : UInt32)) * (1 : UInt32)) + ((x <<< (31 : UInt32)) * (3 : UInt32)) + ((x <<< (32 : UInt32)) * (5 : UInt32)) + ((x <<< (33 : UInt32)) * (7 : UInt32)) + ((y <<< (4294967295 : UInt32)) * (11 : UInt32))
private def rightReference (x y : UInt32) : UInt32 :=
  ((x >>> (0 : UInt32)) * (1 : UInt32)) + ((x >>> (31 : UInt32)) * (3 : UInt32)) + ((x >>> (32 : UInt32)) * (5 : UInt32)) + ((x >>> (33 : UInt32)) * (7 : UInt32)) + ((y >>> (4294967295 : UInt32)) * (11 : UInt32))

-- Each row removes one actual summand, then replaces only that count by a wrong count.
-- Non-equality witnesses prove that all ten claimed boundary operations are observable.
private def sensitive (reference term replacement : UInt32) : Prop :=
  reference ≠ reference - term ∧ reference ≠ reference - term + replacement
private theorem each_operation :
  sensitive (leftReference 1 0) (((1 : UInt32) <<< (0 : UInt32)) * (1 : UInt32)) (((1 : UInt32) <<< (1 : UInt32)) * (1 : UInt32)) ∧
  sensitive (leftReference 1 0) (((1 : UInt32) <<< (31 : UInt32)) * (3 : UInt32)) (((1 : UInt32) <<< (30 : UInt32)) * (3 : UInt32)) ∧
  sensitive (leftReference 1 0) (((1 : UInt32) <<< (32 : UInt32)) * (5 : UInt32)) (((1 : UInt32) <<< (31 : UInt32)) * (5 : UInt32)) ∧
  sensitive (leftReference 1 0) (((1 : UInt32) <<< (33 : UInt32)) * (7 : UInt32)) (((1 : UInt32) <<< (0 : UInt32)) * (7 : UInt32)) ∧
  sensitive (leftReference 0 1) (((1 : UInt32) <<< (4294967295 : UInt32)) * (11 : UInt32)) (((1 : UInt32) <<< (30 : UInt32)) * (11 : UInt32)) ∧
  sensitive (rightReference 1 0) (((1 : UInt32) >>> (0 : UInt32)) * (1 : UInt32)) (((1 : UInt32) >>> (1 : UInt32)) * (1 : UInt32)) ∧
  sensitive (rightReference 2147483648 0) (((2147483648 : UInt32) >>> (31 : UInt32)) * (3 : UInt32)) (((2147483648 : UInt32) >>> (30 : UInt32)) * (3 : UInt32)) ∧
  sensitive (rightReference 1 0) (((1 : UInt32) >>> (32 : UInt32)) * (5 : UInt32)) (((1 : UInt32) >>> (31 : UInt32)) * (5 : UInt32)) ∧
  sensitive (rightReference 2 0) (((2 : UInt32) >>> (33 : UInt32)) * (7 : UInt32)) (((2 : UInt32) >>> (0 : UInt32)) * (7 : UInt32)) ∧
  sensitive (rightReference 0 2147483648) (((2147483648 : UInt32) >>> (4294967295 : UInt32)) * (11 : UInt32)) (((2147483648 : UInt32) >>> (30 : UInt32)) * (11 : UInt32)) := by
  unfold sensitive leftReference rightReference
  decide

-- Correlated errors affecting both encodings of count 31 must also be visible.
private theorem shared_counts :
  (leftReference 1 0 ≠ leftReference 1 0 -
    ((1 : UInt32) <<< (31 : UInt32)) * 3 - ((0 : UInt32) <<< (4294967295 : UInt32)) * 11) ∧
  (leftReference 1 0 ≠ leftReference 1 0 - ((1 : UInt32) <<< (31 : UInt32)) * 3 +
    ((1 : UInt32) <<< (30 : UInt32)) * 3) ∧
  (rightReference 2147483648 0 ≠ rightReference 2147483648 0 -
    ((2147483648 : UInt32) >>> (31 : UInt32)) * 3 - ((0 : UInt32) >>> (4294967295 : UInt32)) * 11) ∧
  (rightReference 2147483648 0 ≠ rightReference 2147483648 0 -
    ((2147483648 : UInt32) >>> (31 : UInt32)) * 3 + ((2147483648 : UInt32) >>> (30 : UInt32)) * 3) ∧
  (leftReference 1 0 ≠ leftReference 1 0 - 1 - 5) ∧
  (rightReference 1 0 ≠ rightReference 1 0 - 1 - 5) := by
  decide

private theorem reference_binding (x y : UInt32) :
    (original (inputMemory x y) 1 0).memory 1 0 = leftReference x y ∧
    (original (inputMemory x y) 1 0).memory 2 0 = rightReference x y := by
  simp [original,inputMemory,store,leftReference,rightReference,
    ShaderIeee.Model.uintAdd,ShaderIeee.Model.uintMultiply,
    ShaderIeee.Model.uintShiftLeft,ShaderIeee.Model.uintShiftRight]

#print axioms reference_binding
#print axioms each_operation
#print axioms shared_counts

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
