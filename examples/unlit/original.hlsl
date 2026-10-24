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
    float3 n = normalize(normalWS);
    float3 v = normalize(viewWS);
    float3 l = normalize(_LightDirection.xyz);

    float diffuse = saturate(dot(n, l));
    float edge = 1.0f - saturate(dot(n, v));
    float rim = edge * edge;

    float3 color = _BaseColor.rgb * (_Ambient + diffuse * _LightColor.rgb);
    color += _RimColor.rgb * rim * _RimStrength;
    return float4(color, _BaseColor.a);
}
