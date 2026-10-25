// Unity CLI eval_file evaluates this body in the existing Editor.
var workspace = @"__WORKSPACE__";
var output = @"__OUTPUT__";
var folder = "Assets/__ASSET_FOLDER__";
var absolute = System.IO.Path.Combine(Application.dataPath, "__ASSET_FOLDER__");
System.IO.Directory.CreateDirectory(absolute);
System.IO.Directory.CreateDirectory(output);
var roles = new[] { "original", "optimized", "wrong" };
var hashes = new Dictionary<string, string>();
var materials = new List<Material>();
var previousTarget = RenderTexture.active;
var previousScene = UnityEngine.SceneManagement.SceneManager.GetActiveScene();
var scene = default(UnityEngine.SceneManagement.Scene);
RenderTexture numeric = null;
RenderTexture sceneTarget = null;
Texture2D readback = null;
Texture2D picture = null;
UnityEngine.Rendering.VolumeProfile profile = null;

Color[] ReadTarget(RenderTexture target)
{
    var old = RenderTexture.active;
    Texture2D texture = null;
    try
    {
        RenderTexture.active = target;
        texture = new Texture2D(target.width, target.height, TextureFormat.RGBAFloat, false, true);
        texture.ReadPixels(new Rect(0, 0, target.width, target.height), 0, 0);
        texture.Apply(false);
        var pixels = texture.GetPixels();
        foreach (var pixel in pixels)
            for (int c = 0; c < 4; c++)
                if (float.IsNaN(pixel[c]) || float.IsInfinity(pixel[c])) throw new Exception("Non-finite GPU readback");
        return pixels;
    }
    finally { RenderTexture.active = old; if (texture != null) UnityEngine.Object.DestroyImmediate(texture); }
}

double[] Unit(Vector3 value)
{
    double length = Math.Sqrt((double)value.x*value.x + (double)value.y*value.y + (double)value.z*value.z);
    if (length == 0) throw new Exception("Invalid zero direction in numeric oracle");
    return new[] { value.x/length, value.y/length, value.z/length };
}

void RenderCamera(Camera camera, RenderTexture destination)
{
    var request = new UnityEngine.Rendering.RenderPipeline.StandardRequest { destination = destination };
    if (!UnityEngine.Rendering.RenderPipeline.SupportsRenderRequest(camera, request)) throw new Exception("HDRP StandardRequest is unavailable");
    UnityEngine.Rendering.RenderPipeline.SubmitRenderRequest(camera, request);
}

try
{
    var template = System.IO.File.ReadAllText(System.IO.Path.Combine(workspace, "__SHADER_TEMPLATE__"));
    foreach (var role in roles)
    {
        var bytes = System.IO.File.ReadAllBytes(System.IO.Path.Combine(workspace, "examples/__EXAMPLE__/"+role+".hlsl"));
        using (var sha = System.Security.Cryptography.SHA256.Create())
            hashes[role] = BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
        System.IO.File.WriteAllBytes(System.IO.Path.Combine(absolute, role+".hlsl"), bytes);
        System.IO.File.WriteAllText(System.IO.Path.Combine(absolute, role+".shader"), template.Replace("__ROLE__",role));
        AssetDatabase.ImportAsset(folder+"/"+role+".hlsl", ImportAssetOptions.ForceSynchronousImport);
        AssetDatabase.ImportAsset(folder+"/"+role+".shader", ImportAssetOptions.ForceSynchronousImport|ImportAssetOptions.ForceUpdate);
        var shader = AssetDatabase.LoadAssetAtPath<Shader>(folder+"/"+role+".shader");
        if (shader == null || !shader.isSupported) throw new Exception("Unavailable material shader: "+role);
        foreach (var message in ShaderUtil.GetShaderMessages(shader))
            if (message.severity.ToString()=="Error") throw new Exception(role+": "+message.message);
        materials.Add(new Material(shader));
    }

    numeric = new RenderTexture(4,4,0,RenderTextureFormat.ARGBFloat,RenderTextureReadWrite.Linear);
    if (!numeric.Create()) throw new Exception("Numeric target creation failed");
    var directions = new[] {new Vector3(0,0,-2), new Vector3(2,0,-1), new Vector3(-3,1,0), new Vector3(0,4,1)};
    var lightDirection = new Vector3(-.4f,.7f,-.6f);
    var baseColor = new Vector4(.9f,.24f,.07f,.8f);
    var lightColor = new Vector4(1,.9f,.8f,1);
    var rimColor = new Vector4(.1f,.7f,1,1);
    // ShaderLab Color properties are converted from sRGB inspector values when
    // Unity binds a material in Linear color space. Compare actual HLSL inputs.
    var baseLinear = QualitySettings.activeColorSpace==ColorSpace.Linear ? ((Color)baseColor).linear : (Color)baseColor;
    var lightLinear = QualitySettings.activeColorSpace==ColorSpace.Linear ? ((Color)lightColor).linear : (Color)lightColor;
    var rimLinear = QualitySettings.activeColorSpace==ColorSpace.Linear ? ((Color)rimColor).linear : (Color)rimColor;
    const double tolerance = 0.0001;
    double maxError = 0, wrongDifference = 0;
    string worstCase = "";
    int numericCases = 0, numericPixels = 0;
    foreach (var normal in directions)
    foreach (var view in directions)
    foreach (var strength in new[] {0f,1.5f,4f})
    foreach (var ambient in new[] {0f,.15f,1f})
    {
        var n=Unit(normal); var v=Unit(view); var l=Unit(lightDirection);
        var diffuse=Math.Min(1,Math.Max(0,n[0]*l[0]+n[1]*l[1]+n[2]*l[2]));
        var edge=1-Math.Min(1,Math.Max(0,n[0]*v[0]+n[1]*v[1]+n[2]*v[2]));
        var expected=new double[4];
        for(int c=0;c<3;c++) expected[c]=baseLinear[c]*(ambient+diffuse*lightLinear[c])+rimLinear[c]*edge*edge*strength;
        expected[3]=baseColor.w;
        Color[][] values = new Color[3][];
        for(int role=0;role<3;role++)
        {
            var material=materials[role];
            material.SetVector("_BaseColor",baseColor); material.SetVector("_LightColor",lightColor); material.SetVector("_RimColor",rimColor);
            material.SetVector("_LightDirection",lightDirection); material.SetFloat("_Ambient",ambient); material.SetFloat("_RimStrength",strength);
            material.SetVector("_ProbeNormal",normal); material.SetVector("_ProbeView",view);
            int numericPass=material.FindPass("NumericProbe");
            if(numericPass<0) throw new Exception("Missing isolated numeric pass");
            Graphics.Blit(Texture2D.whiteTexture,numeric,material,numericPass);
            values[role]=ReadTarget(numeric);
            if(values[role].Length!=16) throw new Exception("Empty numeric GPU output");
        }
        for(int p=0;p<16;p++) for(int c=0;c<4;c++)
        {
            if(Math.Max(Math.Abs(values[0][p][c]-expected[c]),Math.Abs(values[1][p][c]-expected[c]))>maxError)
                worstCase=" normal="+normal+" view="+view+" ambient="+ambient+" strength="+strength+" pixel="+p+" channel="+c+" expected="+expected[c]+" original="+values[0][p]+" optimized="+values[1][p];
            maxError=Math.Max(maxError,Math.Abs(values[0][p][c]-expected[c]));
            maxError=Math.Max(maxError,Math.Abs(values[1][p][c]-expected[c]));
            maxError=Math.Max(maxError,Math.Abs((double)values[0][p][c]-values[1][p][c]));
            wrongDifference=Math.Max(wrongDifference,Math.Abs((double)values[0][p][c]-values[2][p][c]));
        }
        numericCases++; numericPixels+=16;
    }
    if(numericCases==0 || maxError>tolerance || wrongDifference<=tolerance) throw new Exception("Numeric oracle failed: error="+maxError+", wrong="+wrongDifference+worstCase);

    // Persist real material assets, then save/reload a scene that references them.
    for(int role=0;role<2;role++)
    {
        materials[role].SetVector("_BaseColor",new Vector4(.9f,.24f,.07f,1));
        materials[role].SetVector("_LightColor",lightColor); materials[role].SetVector("_RimColor",rimColor);
        materials[role].SetVector("_LightDirection",lightDirection); materials[role].SetFloat("_Ambient",.15f); materials[role].SetFloat("_RimStrength",1.5f);
        var path=folder+"/"+roles[role]+".mat";
        var asset=AssetDatabase.LoadAssetAtPath<Material>(path);
        if(asset==null) { asset=new Material(materials[role]); AssetDatabase.CreateAsset(asset,path); }
        else { asset.shader=materials[role].shader; asset.CopyPropertiesFromMaterial(materials[role]); EditorUtility.SetDirty(asset); }
    }
    scene=UnityEditor.SceneManagement.EditorSceneManager.NewScene(UnityEditor.SceneManagement.NewSceneSetup.EmptyScene,UnityEditor.SceneManagement.NewSceneMode.Additive);
    UnityEngine.SceneManagement.SceneManager.SetActiveScene(scene);
    for(int role=0;role<2;role++)
    {
        var sphere=GameObject.CreatePrimitive(PrimitiveType.Sphere);
        sphere.name=role==0 ? "Original" : "Optimized"; sphere.layer=30;
        sphere.transform.position=new Vector3(role==0 ? -1.2f : 1.2f,0,0);
        sphere.transform.localScale=Vector3.one*2;
        sphere.GetComponent<Renderer>().sharedMaterial=AssetDatabase.LoadAssetAtPath<Material>(folder+"/"+roles[role]+".mat");
        UnityEngine.Object.DestroyImmediate(sphere.GetComponent<Collider>());
    }
    var cameraObject=new GameObject("Material Camera"); cameraObject.layer=30;
    var camera=cameraObject.AddComponent<Camera>(); camera.enabled=false; camera.cullingMask=1<<30;
    camera.transform.position=new Vector3(0,0,-7); camera.transform.rotation=Quaternion.identity;
    camera.fieldOfView=40; camera.nearClipPlane=.1f; camera.farClipPlane=50;
    camera.clearFlags=CameraClearFlags.SolidColor; camera.backgroundColor=new Color(.025f,.025f,.025f,1);
    var hd=cameraObject.AddComponent<UnityEngine.Rendering.HighDefinition.HDAdditionalCameraData>();
    hd.clearColorMode=UnityEngine.Rendering.HighDefinition.HDAdditionalCameraData.ClearColorMode.Color;
    hd.backgroundColorHDR=camera.backgroundColor; hd.volumeLayerMask=1<<30;
    hd.antialiasing=UnityEngine.Rendering.HighDefinition.HDAdditionalCameraData.AntialiasingMode.None;
    // Isolate the material from the sample project's fog/exposure/post effects.
    // These overrides belong only to this saved demo camera, never the asset.
    hd.customRenderingSettings=true;
    foreach(var field in new[] {
        UnityEngine.Rendering.HighDefinition.FrameSettingsField.Postprocess,
        UnityEngine.Rendering.HighDefinition.FrameSettingsField.ExposureControl,
        UnityEngine.Rendering.HighDefinition.FrameSettingsField.AtmosphericScattering })
    {
        hd.renderingPathCustomFrameSettings.SetEnabled(field,false);
        hd.renderingPathCustomFrameSettingsOverrideMask.mask[(uint)field]=true;
    }
    var volumeObject=new GameObject("Fixed Exposure"); volumeObject.layer=30;
    var volume=volumeObject.AddComponent<UnityEngine.Rendering.Volume>(); volume.isGlobal=true; volume.priority=10000;
    var profilePath=folder+"/Exposure.asset";
    profile=AssetDatabase.LoadAssetAtPath<UnityEngine.Rendering.VolumeProfile>(profilePath);
    if(profile==null) { profile=UnityEngine.ScriptableObject.CreateInstance<UnityEngine.Rendering.VolumeProfile>(); AssetDatabase.CreateAsset(profile,profilePath); }
    UnityEngine.Rendering.HighDefinition.Exposure exposure;
    if(!profile.TryGet<UnityEngine.Rendering.HighDefinition.Exposure>(out exposure))
    { exposure=profile.Add<UnityEngine.Rendering.HighDefinition.Exposure>(true); AssetDatabase.AddObjectToAsset(exposure,profile); }
    exposure.mode.Override(UnityEngine.Rendering.HighDefinition.ExposureMode.Fixed); exposure.fixedExposure.Override(0);
    volume.sharedProfile=profile;
    EditorUtility.SetDirty(profile); EditorUtility.SetDirty(exposure); AssetDatabase.SaveAssets();
    var requestedScenePath=folder+"/__SCENE_NAME__.unity";
    var scenePath=requestedScenePath;
    // An Editor may already display the demo. Save validation separately instead of closing it.
    if(UnityEngine.SceneManagement.SceneManager.GetSceneByPath(scenePath).isLoaded)
    {
        scenePath=folder+"/__SCENE_NAME__.Validation.unity";
        if(UnityEngine.SceneManagement.SceneManager.GetSceneByPath(scenePath).isLoaded)
            scenePath=AssetDatabase.GenerateUniqueAssetPath(scenePath);
    }
    camera.enabled=true;
    if(!UnityEditor.SceneManagement.EditorSceneManager.SaveScene(scene,scenePath)) throw new Exception("Scene save failed");
    UnityEngine.SceneManagement.SceneManager.SetActiveScene(previousScene);
    UnityEditor.SceneManagement.EditorSceneManager.CloseScene(scene,true);
    scene=UnityEditor.SceneManagement.EditorSceneManager.OpenScene(scenePath,UnityEditor.SceneManagement.OpenSceneMode.Additive);
    var roots=scene.GetRootGameObjects();
    camera=null; Renderer first=null,second=null;
    foreach(var root in roots)
    {
        if(root.name=="Material Camera") camera=root.GetComponent<Camera>();
        if(root.name=="Original") first=root.GetComponent<Renderer>();
        if(root.name=="Optimized") second=root.GetComponent<Renderer>();
    }
    if(camera==null || first==null || second==null || first.sharedMaterial==null || second.sharedMaterial==null) throw new Exception("Reloaded scene lost references");
    camera.enabled=false;
    // Ordinary loaded scenes share default culling bits, even when Camera.scene is assigned.
    var sceneMask=UnityEditor.SceneManagement.EditorSceneManager.CalculateAvailableSceneCullingMask();
    if(sceneMask==0) throw new Exception("No isolated scene culling mask available");
    UnityEditor.SceneManagement.EditorSceneManager.SetSceneCullingMask(scene,sceneMask);
    camera.overrideSceneCullingMask=sceneMask;
    sceneTarget=new RenderTexture(768,384,24,RenderTextureFormat.ARGBFloat,RenderTextureReadWrite.Linear);
    if(!sceneTarget.Create()) throw new Exception("Scene target creation failed");
    RenderCamera(camera,sceneTarget); RenderCamera(camera,sceneTarget);
    var scenePixels=ReadTarget(sceneTarget);
    int isolationPixels=0;
    first.forceRenderingOff=true; second.forceRenderingOff=true;
    try
    {
        RenderCamera(camera,sceneTarget);
        foreach(var pixel in ReadTarget(sceneTarget))
            if(Math.Max(pixel.r,pixel.b)-pixel.g>.04f) isolationPixels++;
        if(isolationPixels!=0) throw new Exception("Other scene geometry contaminated validation: "+isolationPixels);
    }
    finally {first.forceRenderingOff=false; second.forceRenderingOff=false;}
    int leftPixels=0,rightPixels=0; double minColor=100,maxColor=-100;
    for(int y=0;y<384;y++) for(int x=0;x<768;x++)
    {
        var c=scenePixels[y*768+x];
        if(Math.Max(c.r,c.b)-c.g>.04f)
        { if(x<384) leftPixels++; else rightPixels++; minColor=Math.Min(minColor,c.r); maxColor=Math.Max(maxColor,c.r); }
    }
    picture=new Texture2D(768,384,TextureFormat.RGBA32,false);
    var pngPixels=new Color[scenePixels.Length];
    for(int i=0;i<pngPixels.Length;i++) pngPixels[i]=scenePixels[i].gamma;
    picture.SetPixels(pngPixels); picture.Apply(false);
    System.IO.File.WriteAllBytes(System.IO.Path.Combine(output,"preview.png"),picture.EncodeToPNG());
    if(leftPixels<500 || rightPixels<500 || maxColor-minColor<.05)
    {
        double maxR=0,maxG=0,maxB=0;
        foreach(var pixel in scenePixels) {maxR=Math.Max(maxR,pixel.r);maxG=Math.Max(maxG,pixel.g);maxB=Math.Max(maxB,pixel.b);}
        throw new Exception("HDRP scene camera did not show both shaded spheres: "+leftPixels+","+rightPixels+" maxRGB="+maxR+","+maxG+","+maxB);
    }

    // Compare identical geometry/camera with only the verified source material changed.
    var originalPosition=first.transform.position;
    var originalMaterial=first.sharedMaterial;
    double meshMaxError=0;
    try
    {
        second.forceRenderingOff=true; first.transform.position=Vector3.zero;
        RenderCamera(camera,sceneTarget); var a=ReadTarget(sceneTarget);
        first.sharedMaterial=second.sharedMaterial;
        RenderCamera(camera,sceneTarget); var b=ReadTarget(sceneTarget);
        for(int p=0;p<a.Length;p++) for(int c=0;c<4;c++) meshMaxError=Math.Max(meshMaxError,Math.Abs((double)a[p][c]-b[p][c]));
        if(meshMaxError>tolerance) throw new Exception("Aligned HDRP material images differ: "+meshMaxError);
    }
    finally { first.transform.position=originalPosition; first.sharedMaterial=originalMaterial; second.forceRenderingOff=false; }
    return new {status="PASSED", unity=Application.unityVersion, graphics=SystemInfo.graphicsDeviceType.ToString(), hashes,
        numericCases,numericPixels,tolerance,maxError,wrongDifference,meshMaxError,leftPixels,rightPixels,scenePath,requestedScenePath,
        sceneReloaded=true,sceneCamera="HDRP RenderPipeline.StandardRequest",sceneIsolation=true,isolationPixels,preview="preview.png",
        guarantee="Finite GPU/CPU and saved-scene HDRP checks; Lean separately proves fragment real-number equivalence"};
}
finally
{
    RenderTexture.active=previousTarget;
    if(previousScene.IsValid() && previousScene.isLoaded) UnityEngine.SceneManagement.SceneManager.SetActiveScene(previousScene);
    if(scene.IsValid() && scene.isLoaded) UnityEditor.SceneManagement.EditorSceneManager.CloseScene(scene,true);
    foreach(var material in materials) UnityEngine.Object.DestroyImmediate(material);
    if(numeric!=null) {numeric.Release(); UnityEngine.Object.DestroyImmediate(numeric);}
    if(sceneTarget!=null) {sceneTarget.Release(); UnityEngine.Object.DestroyImmediate(sceneTarget);}
    if(readback!=null) UnityEngine.Object.DestroyImmediate(readback);
    if(picture!=null) UnityEngine.Object.DestroyImmediate(picture);
}
