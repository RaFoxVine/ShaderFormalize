import Lake
open Lake DSL

package shaderformalize

require mathlib from git
  "https://github.com/leanprover-community/mathlib4.git" @
  "f897ebcf72cd16f89ab4577d0c826cd14afaafc7"

lean_exe fetchMathlibCache where
  root := `ShaderFormalize.FetchCache

@[default_target]
lean_lib ShaderFormalize where
  roots := #[`ShaderFormalize.Model, `ShaderFormalize.Fragment, `ShaderFormalize.Control, `GeneratedModel, `SubmittedProof]
