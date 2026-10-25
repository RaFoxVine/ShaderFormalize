import ShaderFormalize.Control
import Mathlib.Tactic.FinCases

namespace ShaderFormalize.Packing

-- Only the generated guarded domain makes this total Lean function an HLSL cast.
noncomputable def ofReal (x : ℝ) : BitVec 32 := BitVec.ofNat 32 ⌊x⌋₊

-- Totalization outside the proved count<32 domain keeps large counts bounded.
def shiftLeft (value count : BitVec 32) : BitVec 32 := value <<< (count.toNat % 32)
def shiftRight (value count : BitVec 32) : BitVec 32 := value >>> (count.toNat % 32)

theorem unpack_low (a b : BitVec 32) :
    (((a &&& 255) ||| ((b &&& 255) <<< 8)) &&& 255) = (a &&& 255) := by
  apply BitVec.eq_of_getLsbD_eq
  intro i hi
  have bits : ∀ j : Fin 32,
      (((a &&& 255) ||| ((b &&& 255) <<< 8)) &&& 255).getLsbD j.val =
        (a &&& 255).getLsbD j.val := by
    intro j
    fin_cases j <;> simp [BitVec.getLsbD_and, BitVec.getLsbD_or,
      BitVec.getLsbD_shiftLeft, BitVec.getLsbD_ofNat]
  exact bits ⟨i, hi⟩

theorem unpack_high (a b : BitVec 32) :
    ((((a &&& 255) ||| ((b &&& 255) <<< 8)) >>> 8) &&& 255) = (b &&& 255) := by
  apply BitVec.eq_of_getLsbD_eq
  intro i hi
  have bits : ∀ j : Fin 32,
      ((((a &&& 255) ||| ((b &&& 255) <<< 8)) >>> 8) &&& 255).getLsbD j.val =
        (b &&& 255).getLsbD j.val := by
    intro j
    fin_cases j <;> simp [BitVec.getLsbD_and, BitVec.getLsbD_or,
      BitVec.getLsbD_shiftLeft, BitVec.getLsbD_ushiftRight, BitVec.getLsbD_ofNat]
  exact bits ⟨i, hi⟩

end ShaderFormalize.Packing
