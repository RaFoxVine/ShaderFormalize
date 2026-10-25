import ShaderFormalize.Fragment

namespace ShaderFormalize.Control
open ShaderFormalize.Model

-- A mask describes execution positions; ordinary fields retain all input values.
noncomputable def finish {E : Type} (alive : E → Prop) (color : E → Vec4) : E → Option Vec4 :=
  ShaderFormalize.Fragment.finish [alive] color

end ShaderFormalize.Control
