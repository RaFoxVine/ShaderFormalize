// Exact source bytes are shared by the Lean import and this Unity material.
var workspace = @"__WORKSPACE__";
var output = @"__OUTPUT__";
bool branched = "__EXAMPLE__" == "branched";
var folder = "Assets/__ASSET_FOLDER__";
var absolute = System.IO.Path.Combine(Application.dataPath,"__ASSET_FOLDER__");
System.IO.Directory.CreateDirectory(absolute);
System.IO.Directory.CreateDirectory(output);
var roles = branched ? new[] {"original","optimized","wrong","wrong-cutoff"} : new[] {"original","optimized","wrong","wrong-uv","wrong-derivative","wrong-lod","wrong-sampler"};
var hashes = new Dictionary<string,string>();
var materials = new List<Material>();
var previousTarget = RenderTexture.active;
var previousScene = UnityEngine.SceneManagement.SceneManager.GetActiveScene();
var scene = default(UnityEngine.SceneManagement.Scene);
RenderTexture numeric = null;
RenderTexture sceneTarget = null;
Texture2D picture = null;
Texture2D readback = null;
Texture2D generatedTexture = null;
UnityEngine.Rendering.VolumeProfile profile = null;
Color[] ReadTarget(RenderTexture target)
{
    var old=RenderTexture.active;
    Texture2D texture=null;
    try
    {
        RenderTexture.active=target;
        texture=new Texture2D(target.width,target.height,TextureFormat.RGBAFloat,false,true);
        texture.ReadPixels(new Rect(0,0,target.width,target.height),0,0); texture.Apply(false);
        var pixels=texture.GetPixels();
        foreach(var pixel in pixels) for(int c=0;c<4;c++)
            if(float.IsNaN(pixel[c]) || float.IsInfinity(pixel[c])) throw new Exception("Non-finite GPU output");
        return pixels;
    }
    finally {RenderTexture.active=old;if(texture!=null)UnityEngine.Object.DestroyImmediate(texture);}
}
void RenderCamera(Camera camera,RenderTexture destination)
{
    var request=new UnityEngine.Rendering.RenderPipeline.StandardRequest {destination=destination};
    if(!UnityEngine.Rendering.RenderPipeline.SupportsRenderRequest(camera,request)) throw new Exception("HDRP StandardRequest unavailable");
    UnityEngine.Rendering.RenderPipeline.SubmitRenderRequest(camera,request);
}
Color Texel(int x,int y,int level)
{
    int size=16>>level;
    if(level==0) return new Color(.25f+.5f*(x+.5f)/size,.02f+.1f*(y+.5f)/size,.03f+((x+y)%4)*.01f,((x+2*y)%5)*.25f);
    return new Color(.2f+.1f*level+.3f*(x+.5f)/size,.04f+.02f*level,.02f+.03f*(y+.5f)/size,1);
}
Color SamplePoint(double u,double v,int mip)
{
    int size=16>>mip;
    int x=(int)Math.Floor((u-Math.Floor(u))*size);
    int y=(int)Math.Floor((v-Math.Floor(v))*size);
    return Texel(x,y,mip);
}
void DrawNumeric(Material material,int pass,RenderTexture target)
{
    var old=RenderTexture.active;
    try
    {
        RenderTexture.active=target;
        GL.Clear(false,true,new Color(-2,-2,-2,-2));
        Graphics.Blit(Texture2D.whiteTexture,target,material,pass);
    }
    finally {RenderTexture.active=old;}
}
try
{
    var template=System.IO.File.ReadAllText(System.IO.Path.Combine(workspace,"__SHADER_TEMPLATE__"));
    foreach(var role in roles)
    {
        var bytes=System.IO.File.ReadAllBytes(System.IO.Path.Combine(workspace,"examples/__EXAMPLE__/"+role+".hlsl"));
        using(var sha=System.Security.Cryptography.SHA256.Create()) hashes[role]=BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-","").ToLowerInvariant();
        System.IO.File.WriteAllBytes(System.IO.Path.Combine(absolute,role+".hlsl"),bytes);
        System.IO.File.WriteAllText(System.IO.Path.Combine(absolute,role+".shader"),template.Replace("__ROLE__",role));
        AssetDatabase.ImportAsset(folder+"/"+role+".hlsl",ImportAssetOptions.ForceSynchronousImport);
        AssetDatabase.ImportAsset(folder+"/"+role+".shader",ImportAssetOptions.ForceSynchronousImport|ImportAssetOptions.ForceUpdate);
        var shader=AssetDatabase.LoadAssetAtPath<Shader>(folder+"/"+role+".shader");
        if(shader==null || !shader.isSupported) throw new Exception("Unavailable shader: "+role);
        foreach(var message in ShaderUtil.GetShaderMessages(shader))
            if(message.severity.ToString()=="Error") throw new Exception(role+": "+message.message);
        materials.Add(new Material(shader));
    }
    generatedTexture=new Texture2D(16,16,TextureFormat.RGBAFloat,true,true);
    generatedTexture.name="Controlled mip texture";generatedTexture.filterMode=FilterMode.Point;generatedTexture.wrapMode=TextureWrapMode.Repeat;generatedTexture.anisoLevel=0;
    for(int mip=0;mip<generatedTexture.mipmapCount;mip++)
    {
        int size=16>>mip;var texels=new Color[size*size];
        for(int y=0;y<size;y++)for(int x=0;x<size;x++)texels[y*size+x]=Texel(x,y,mip);
        generatedTexture.SetPixels(texels,mip);
    }
    generatedTexture.Apply(false,false);
    var texturePath=folder+"/ControlledTexture.asset";
    var textureAsset=AssetDatabase.LoadAssetAtPath<Texture2D>(texturePath);
    if(textureAsset==null) {textureAsset=generatedTexture;AssetDatabase.CreateAsset(textureAsset,texturePath);generatedTexture=null;}
    else {EditorUtility.CopySerialized(generatedTexture,textureAsset);EditorUtility.SetDirty(textureAsset);}
    var tint=new Vector4(.9f,.3f,.1f,1);
    var transform=new Vector4(1,2,.03125f,.015625f);
    foreach(var material in materials)
    {
        material.SetTexture("_BaseMap",textureAsset);material.SetVector("_Tint",tint);material.SetVector("_UVTransform",transform);if(!branched)material.SetFloat("_DetailStrength",.35f);
    }
    const int width=64,height=32;
    const double tolerance=.0001;
    numeric=new RenderTexture(width,height,0,RenderTextureFormat.ARGBFloat,RenderTextureReadWrite.Linear);
    if(!numeric.Create())throw new Exception("Numeric target creation failed");
    int calibrationPass=materials[0].FindPass("UVCalibration");
    if(calibrationPass<0)throw new Exception("Missing UV calibration pass");
    DrawNumeric(materials[0],calibrationPass,numeric);var coordinates=ReadTarget(numeric);
    double uvGridError=0;
    // Validate the wrapper's interpolated UVs as a regular grid, allowing API origin reversal.
    bool flipped=coordinates[0].g>.5f;
    for(int y=0;y<height;y++)for(int x=0;x<width;x++)
    {
        int p=y*width+x;double v=flipped?1-(y+.5)/height:(y+.5)/height;
        uvGridError=Math.Max(uvGridError,Math.Abs(coordinates[p].r-(x+.5)/width));
        uvGridError=Math.Max(uvGridError,Math.Abs(coordinates[p].g-v));
    }
    if(uvGridError>1e-6)throw new Exception("Unexpected raster UV grid: "+uvGridError);
    double dx=transform.x/width,dy=transform.y/height;
    // Max footprint in texture texels is exactly 1: point sampled implicit/Grad mip0.
    if(Math.Max(Math.Abs(dx),Math.Abs(dy))*16>1.000001)throw new Exception("CPU oracle LOD premise broken");
    double footprint=dx*dx+dy*dy;
    double maxError=0,wrongDifference=0;
    var negativeColorDifference=new Dictionary<string,double>();var negativeMaskDifference=new Dictionary<string,int>();
    foreach(var role in roles.Skip(2)){negativeColorDifference[role]=0;negativeMaskDifference[role]=0;}
    int numericCases=0,numericPixels=0,keptPixels=0,discardedPixels=0,boundaryKeptPixels=0;
    string worstCase="";
    foreach(float cutoff in new[]{0f,.5f,.75f,1f})foreach(float bottom in new[]{0f,.25f})foreach(int mip in (branched?new[]{0}:new[]{0,1,2}))
    foreach(float useTexture in (branched?new[]{0f,.5f,1f}:new[]{1f}))foreach(float mode in (branched?new[]{0f,.5f,1f,1.5f,2f}:new[]{0f}))
    {
        var values=new Color[roles.Length][];
        for(int role=0;role<roles.Length;role++)
        {
            var material=materials[role];material.SetFloat("_Cutoff",cutoff);material.SetFloat("_Bottom",bottom);if(!branched)material.SetFloat("_Mip",mip);else{material.SetFloat("_UseTexture",useTexture);material.SetFloat("_Mode",mode);}
            int pass=material.FindPass("NumericProbe");if(pass<0)throw new Exception("Missing numeric pass");
            DrawNumeric(material,pass,numeric);values[role]=ReadTarget(numeric);
        }
        for(int p=0;p<width*height;p++)
        {
            double u=coordinates[p].r*transform.x+transform.z,v=coordinates[p].g*transform.y+transform.w;
            var sample=SamplePoint(u,v,0);var detail=SamplePoint(u,v,mip);
            bool keep=(!branched || useTexture>.5f ? sample.a>=cutoff : true) && coordinates[p].g>=bottom;
            var expected=new double[4];
            if(branched)
            {
                var baseValue=useTexture>.5f?sample:(Color)tint;
                for(int c=0;c<3;c++)
                    expected[c]=mode<.5f ? baseValue[c]*tint[c]*(.5+footprint) : mode<1.5f ? (baseValue[c]+tint[c])*(.25+footprint) : (baseValue[c]+tint[c])*.5*(1+footprint);
                expected[3]=useTexture>.5f && mode<1.5f ? baseValue.a : tint.w;
            }
            else
            {
                for(int c=0;c<3;c++)expected[c]=(sample[c]*tint[c]+(detail[c]+sample[c])*.35f)*(.5+footprint);
                expected[3]=sample.a*tint.w;
            }
            for(int role=0;role<2;role++)
            {
                bool actualKeep=values[role][p].a>=0;
                if(actualKeep!=keep)throw new Exception("CPU/GPU discard mask differs: role="+roles[role]+" pixel="+p+" cutoff="+cutoff+" alpha="+sample.a+" GPU="+values[role][p]);
                if(keep)for(int c=0;c<4;c++)
                {
                    double error=Math.Abs(values[role][p][c]-expected[c]);
                    if(error>maxError){maxError=error;worstCase=" pixel="+p+" mip="+mip+" cutoff="+cutoff+" expected="+expected[c]+" actual="+values[role][p];}
                }
            }
            if(keep){keptPixels++;if(sample.a==cutoff)boundaryKeptPixels++;}else discardedPixels++;
            for(int role=2;role<roles.Length;role++)
            {
                bool originalKeep=values[0][p].a>=0,otherKeep=values[role][p].a>=0;
                if(originalKeep!=otherKeep)negativeMaskDifference[roles[role]]++;
                else if(originalKeep)for(int c=0;c<4;c++)negativeColorDifference[roles[role]]=Math.Max(negativeColorDifference[roles[role]],Math.Abs((double)values[0][p][c]-values[role][p][c]));
            }
        }
        numericCases++;numericPixels+=width*height;
    }
    foreach(var role in roles.Skip(2))
    {
        wrongDifference=Math.Max(wrongDifference,negativeColorDifference[role]);
        if(negativeColorDifference[role]<=tolerance && negativeMaskDifference[role]==0)throw new Exception("Undetected negative control: "+role);
    }
    if(maxError>tolerance || keptPixels==0 || discardedPixels==0 || boundaryKeptPixels==0)throw new Exception("Texture/derivative/clip oracle failed: "+maxError+worstCase);
    // Persist real material assets, then save/reload a scene that references them.
    for(int role=0;role<2;role++)
    {
        materials[role].SetFloat("_Cutoff",.5f);materials[role].SetFloat("_Bottom",.15f);if(!branched)materials[role].SetFloat("_Mip",1);else{materials[role].SetFloat("_UseTexture",1);materials[role].SetFloat("_Mode",0);}
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
        numericCases,numericPixels,keptPixels,discardedPixels,boundaryKeptPixels,uvGridError,tolerance,maxError,wrongDifference,negativeColorDifference,negativeMaskDifference,meshMaxError,leftPixels,rightPixels,scenePath,requestedScenePath,
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
    if(generatedTexture!=null) UnityEngine.Object.DestroyImmediate(generatedTexture);
}
