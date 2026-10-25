cbuffer UnityPerMaterial : register(b0)
{
    float4 _BaseColor;
    float4 _LightColor;
    float4 _RimColor;
    float4 _LightDirection;
    float _Ambient;
    float _RimStrength;
};

struct GeometryInput
{
    float3 normalWS : NORMAL0;
    float3 viewWS : TEXCOORD0;
};
struct PSInput { GeometryInput geometry; };
struct LightingTerms { float diffuse; float rim; };
struct SurfaceData { float3 color; float alpha; LightingTerms lighting; };

void EvaluateLighting(GeometryInput geometry, out LightingTerms terms, float rimScale = 1.0)
{
    float3 normal = normalize(geometry.normalWS);
    float3 view = normalize(geometry.viewWS);
    float3 light = normalize(_LightDirection.xyz);
    terms.diffuse = saturate(dot(normal, light));
    float edge = 1.0 - saturate(dot(normal, view));
    terms.rim = edge * edge * rimScale;
}

void Initialize(out SurfaceData surface)
{
    surface.color = _BaseColor.rgb;
    surface.alpha = _BaseColor.a;
    surface.lighting.diffuse = 0.0;
    surface.lighting.rim = 0.0;
}

SurfaceData BuildSurface(PSInput input)
{
    SurfaceData surface;
    Initialize(surface);
    EvaluateLighting(input.geometry, surface.lighting);
    return surface;
}

void AddRim(inout float3 rgb, float rim, float strength = _RimStrength)
{
    rgb += _RimColor.rgb * rim * strength;
}

float4 ShadeSurface(SurfaceData surface)
{
    float3 rgb = surface.color * (_Ambient + surface.lighting.diffuse * _LightColor.rgb);
    AddRim(rgb, surface.lighting.rim);
    return float4(rgb, surface.alpha);
}

float4 main(PSInput input) : SV_Target
{
    SurfaceData surface = BuildSurface(input);
    return ShadeSurface(surface);
}
