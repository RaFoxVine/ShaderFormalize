import ShaderFormalize.Model

namespace ShaderFormalize.Fragment
open ShaderFormalize.Model

-- Predicates refer to immutable fields at the clipping statement, in source order.
abbrev Context (E : Type) := List (E → Prop)

-- These are arbitrary shared parameters, not axioms or a physical filtering model.
-- Whole fields preserve the computation supplied to derivatives and implicit LOD.
structure Ops (E : Type) where
  derivative : String → Context E → (E → ℝ) → E → ℝ
  sample : String → String → Context E → (E → Vec 2) → E → Vec4
  sampleLevel : String → String → Context E → (E → Vec 2) → (E → ℝ) → E → Vec4
  sampleGrad : String → String → Context E → (E → Vec 2) → (E → Vec 2) → (E → Vec 2) → E → Vec4

noncomputable def finish {E : Type} (context : Context E) (color : E → Vec4) : E → Option Vec4 := by
  classical
  exact fun x => if ∀ predicate ∈ context, predicate x then some (color x) else none

end ShaderFormalize.Fragment
