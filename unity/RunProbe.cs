// Executed by Unity CLI eval_file in the existing Editor; placeholders are local paths.

var workspace = @"__WORKSPACE__";
var output = @"__OUTPUT__";
var assetFolder = "Assets/ShaderFormalizeProbe";
var assetAbsolute = System.IO.Path.Combine(Application.dataPath, "ShaderFormalizeProbe");
System.IO.Directory.CreateDirectory(assetAbsolute);
System.IO.Directory.CreateDirectory(output);
var roles = new[] { "original", "optimized", "wrong" };
var hashes = new Dictionary<string, string>();
var materials = new List<Material>();
RenderTexture target = null;
Texture2D readback = null;
var previous = RenderTexture.active;
try
{
    foreach (var role in roles)
    {
        var bytes = System.IO.File.ReadAllBytes(System.IO.Path.Combine(workspace, "examples/lerp/" + role + ".hlsl"));
        using (var sha = System.Security.Cryptography.SHA256.Create())
            hashes[role] = BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
        System.IO.File.WriteAllBytes(System.IO.Path.Combine(assetAbsolute, role + ".hlsl"), bytes);
        var shaderText = "Shader \"Hidden/ShaderFormalize/" + role + "\" { SubShader { Pass { Cull Off ZWrite Off ZTest Always Blend Off\n" +
            "HLSLPROGRAM\n#pragma target 5.0\n#pragma vertex vert_img\n#pragma fragment Frag\n" +
            "#include \"UnityCG.cginc\"\nfloat4 _A; float4 _B; float _T;\n" +
            "#include \"" + role + ".hlsl\"\n" +
            "float4 Frag(v2f_img input) : SV_Target { return main(_A, _B, _T); }\nENDHLSL\n} } }";
        System.IO.File.WriteAllText(System.IO.Path.Combine(assetAbsolute, role + ".shader"), shaderText);
        AssetDatabase.ImportAsset(assetFolder + "/" + role + ".hlsl", ImportAssetOptions.ForceSynchronousImport);
        AssetDatabase.ImportAsset(assetFolder + "/" + role + ".shader", ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
        var shader = AssetDatabase.LoadAssetAtPath<Shader>(assetFolder + "/" + role + ".shader");
        if (shader == null || !shader.isSupported) throw new Exception("Shader unavailable: " + role);
        foreach (var message in ShaderUtil.GetShaderMessages(shader))
            if (message.severity.ToString() == "Error") throw new Exception(role + ": " + message.message);
        materials.Add(new Material(shader));
    }
    target = new RenderTexture(4, 4, 0, RenderTextureFormat.ARGBFloat, RenderTextureReadWrite.Linear);
    if (!target.Create()) throw new Exception("Could not create float render target");
    readback = new Texture2D(4, 4, TextureFormat.RGBAFloat, false, true);
    var values = new[] { 0f, 0.125f, 0.5f, 0.875f, 1f, -0.5f, 1.5f };
    var colorsA = new[] { new Vector4(0, .25f, .75f, 1), new Vector4(-2, 3, .1234f, .9f) };
    var colorsB = new[] { new Vector4(1, .8f, .1f, 0), new Vector4(4, -1, .8765f, .2f) };
    const double tolerance = 0.00001;
    double maxError = 0, wrongDifference = 0, outsideDifference = 0;
    int validPixels = 0, validCases = 0;
    var cases = new List<object>();
    for (int pair = 0; pair < colorsA.Length; pair++)
    foreach (var t in values)
    {
        var results = new Color[3][];
        for (int role = 0; role < 3; role++)
        {
            materials[role].SetVector("_A", colorsA[pair]);
            materials[role].SetVector("_B", colorsB[pair]);
            materials[role].SetFloat("_T", t);
            Graphics.Blit(Texture2D.whiteTexture, target, materials[role]);
            RenderTexture.active = target;
            readback.ReadPixels(new Rect(0, 0, 4, 4), 0, 0);
            readback.Apply(false);
            results[role] = readback.GetPixels();
            if (results[role].Length != 16) throw new Exception("Empty/incomplete GPU readback");
        }
        double caseError = 0;
        bool inRange = t >= 0 && t <= 1;
        for (int pixel = 0; pixel < 16; pixel++)
        for (int c = 0; c < 4; c++)
        {
            for (int role = 0; role < 3; role++)
                if (float.IsNaN(results[role][pixel][c]) || float.IsInfinity(results[role][pixel][c]))
                    throw new Exception("Non-finite GPU result");
            var expected = (double)colorsA[pair][c] + ((double)colorsB[pair][c] - colorsA[pair][c]) * t;
            var difference = Math.Abs((double)results[0][pixel][c] - results[1][pixel][c]);
            if (inRange)
            {
                caseError = Math.Max(caseError, Math.Max(difference,
                    Math.Max(Math.Abs(results[0][pixel][c] - expected), Math.Abs(results[1][pixel][c] - expected))));
                wrongDifference = Math.Max(wrongDifference, Math.Abs((double)results[0][pixel][c] - results[2][pixel][c]));
            }
            else outsideDifference = Math.Max(outsideDifference, difference);
        }
        if (inRange) { validCases++; validPixels += 16; maxError = Math.Max(maxError, caseError); }
        cases.Add(new { pair, t, inRange, maxError = caseError });
    }
    if (validPixels == 0 || maxError > tolerance || wrongDifference <= tolerance || outsideDifference <= tolerance)
        throw new Exception("GPU oracle failed: error=" + maxError + ", wrong=" + wrongDifference + ", outside=" + outsideDifference);
    return new { status = "PASSED", unity = Application.unityVersion, graphics = SystemInfo.graphicsDeviceType.ToString(),
        colorSpace = QualitySettings.activeColorSpace.ToString(), hashes, validCases, validPixels,
        tolerance, maxError, wrongDifference, outsideDifference, cases,
        guarantee = "finite GPU samples with tolerance; formal proof is checked separately by Lean" };
}
finally
{
    RenderTexture.active = previous;
    foreach (var material in materials) UnityEngine.Object.DestroyImmediate(material);
    if (readback != null) UnityEngine.Object.DestroyImmediate(readback);
    if (target != null) { target.Release(); UnityEngine.Object.DestroyImmediate(target); }
}
