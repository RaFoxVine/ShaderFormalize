import ShaderIeee.GeneratedModel

namespace ShaderIeee.AgentProof

private theorem return_two {α : Type} (condition : Bool) (yes no fallback : α) :
    (if condition then yes else if !condition then no else fallback) =
      (if condition then yes else no) := by
  cases condition <;> rfl

private theorem return_three {α : Type} (first second : Bool) (a b c fallback : α) :
    (if first then a else if !first && second then b else if !first && !second then c else fallback) =
      (if first then a else if second then b else c) := by
  cases first <;> cases second <;> rfl

theorem equivalent : ShaderIeee.Generated.expected := by
  unfold ShaderIeee.Generated.expected
  intro input
  funext i
  fin_cases i <;>
    simp only [Generated.original, Generated.optimized, Bool.true_and,
      return_two, return_three, Model.asfloat_asuint]

end ShaderIeee.AgentProof
