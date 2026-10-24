import Mathlib.Data.Real.Basic

namespace ShaderFormalize.Model

abbrev Vec4 := Fin 4 → ℝ

def saturate (x : ℝ) : ℝ := min 1 (max 0 x)

def lerp (a b t : ℝ) : ℝ := a + (b - a) * t

theorem saturate_of_range (x : ℝ) (hlo : 0 ≤ x) (hhi : x ≤ 1) :
    saturate x = x := by
  unfold saturate
  rw [max_eq_right hlo, min_eq_right hhi]

end ShaderFormalize.Model
