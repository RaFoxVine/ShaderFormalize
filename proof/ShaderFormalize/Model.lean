import Mathlib.Data.Real.Sqrt

namespace ShaderFormalize.Model

abbrev Vec (n : Nat) := Fin n → ℝ
abbrev Vec4 := Vec 4

def dot {n : Nat} (a b : Vec n) : ℝ := ∑ i, a i * b i

-- HLSL normalize is only specified for nonzero vectors. The generated theorem
-- receives explicit positive squared-length premises checked by the importer.
noncomputable def normalize {n : Nat} (a : Vec n) : Vec n := fun i => a i / Real.sqrt (dot a a)

def saturate (x : ℝ) : ℝ := min 1 (max 0 x)

def lerp (a b t : ℝ) : ℝ := a + (b - a) * t

theorem saturate_of_range (x : ℝ) (hlo : 0 ≤ x) (hhi : x ≤ 1) :
    saturate x = x := by
  unfold saturate
  rw [max_eq_right hlo, min_eq_right hhi]

end ShaderFormalize.Model
