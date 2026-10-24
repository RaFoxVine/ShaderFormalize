cbuffer UnityPerMaterial : register(b0)
{
    float4 _BaseColor;
    float4 _LightColor;
    float4 _RimColor;
    float4 _LightDirection;
    float _Ambient;
    float _RimStrength;
};

float4 main(float3 normalWS : NORMAL0, float3 viewWS : TEXCOORD0) : SV_Target
{
    float3 normal = normalize(normalWS);
    float diffuse = saturate(dot(normal, normalize(_LightDirection.xyz)));
    float edge = 1.0f - saturate(dot(normal, normalize(viewWS)));
    float rimWeight = _RimStrength * edge * edge;

    float3 albedo = _BaseColor.xyz;
    float3 color = albedo * _Ambient;
    color = color + albedo * _LightColor.xyz * diffuse;
    color += _RimColor.xyz * rimWeight;
    return float4(color, _BaseColor.w);
}
