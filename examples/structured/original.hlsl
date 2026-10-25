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

LightingTerms EvaluateLighting(GeometryInput geometry)
{
    float3 normal = normalize(geometry.normalWS);
    float3 view = normalize(geometry.viewWS);
    float3 light = normalize(_LightDirection.xyz);
    LightingTerms terms;
    terms.diffuse = saturate(dot(normal, light));
    float edge = 1.0f - saturate(dot(normal, view));
    terms.rim = edge * edge;
    return terms;
}

SurfaceData BuildSurface(PSInput input)
{
    SurfaceData surface;
    surface.color = _BaseColor.rgb;
    surface.alpha = _BaseColor.a;
    surface.lighting = EvaluateLighting(input.geometry);
    return surface;
}

float4 ShadeSurface(SurfaceData surface)
{
    surface.color *= _Ambient + surface.lighting.diffuse * _LightColor.rgb;
    surface.color += _RimColor.rgb * surface.lighting.rim * _RimStrength;
    return float4(surface.color, surface.alpha);
}

float4 main(PSInput input) : SV_Target
{
    SurfaceData surface = BuildSurface(input);
    return ShadeSurface(surface);
}
