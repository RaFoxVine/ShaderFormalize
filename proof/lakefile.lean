import Lake
open Lake DSL

package shaderformalize where
  fixedToolchain := true

require mathlib from git
  "https://github.com/leanprover-community/mathlib4" @
  "56a005855ea17e0b0958f73ec801ae140b0a1679"

require floatlib from git
  "https://github.com/lean-dojo/FloatLib.git" @
  "8c8871576a941a86e73dcf0882702b823139aa93"

@[default_target]
lean_lib ShaderFormalize where
  roots := #[`ShaderFormalize.Model, `ShaderFormalize.Fragment, `ShaderFormalize.Control, `ShaderFormalize.Packing, `GeneratedModel, `SubmittedProof]

lean_lib ShaderIeee where
  roots := #[`ShaderIeee.Model, `ShaderIeee.Probe]
