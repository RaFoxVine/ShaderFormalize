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
struct LightWeights { float diffuse; float rim; };
struct MaterialValues { float3 albedo; float opacity; LightWeights weights; };

float Square(float x) { return x * x; }

LightWeights GetWeights(GeometryInput geometry)
{
    float3 n = normalize(geometry.normalWS);
    LightWeights weights;
    weights.diffuse = saturate(dot(n, normalize(_LightDirection.xyz)));
    weights.rim = Square(1.0f - saturate(dot(n, normalize(geometry.viewWS))));
    return weights;
}

MaterialValues ReadMaterial(PSInput input)
{
    MaterialValues material;
    material.albedo = _BaseColor.xyz;
    material.opacity = _BaseColor.w;
    material.weights = GetWeights(input.geometry);
    return material;
}

float4 Compose(MaterialValues material)
{
    MaterialValues copy = material;
    float3 rgb = copy.albedo * _Ambient;
    rgb += copy.albedo * _LightColor.xyz * copy.weights.diffuse;
    float rimWeight = _RimStrength * copy.weights.rim;
    rgb += _RimColor.xyz * rimWeight;
    return float4(rgb, material.opacity);
}

float4 main(PSInput input) : SV_Target
{
    MaterialValues material = ReadMaterial(input);
    return Compose(material);
}
