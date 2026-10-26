import Lake
open Lake DSL

package shaderIeeePrototype where
  version := v!"0.1.0"
  fixedToolchain := true

require floatlib from git
  "https://github.com/lean-dojo/FloatLib.git" @ "8c8871576a941a86e73dcf0882702b823139aa93"

@[default_target]
lean_exe ieeeProbe where
  root := `Main
