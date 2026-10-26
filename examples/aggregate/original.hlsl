cbuffer Material : register(b0)
{
    float2x2 _ColorMix;
    float3 _LightColors[2];
    float4 _BaseColor;
    float _RimStrength;
};
struct PSInput
{
    float3 normalWS : NORMAL0;
    float3 viewWS : TEXCOORD0;
};
struct LightData { float3 color; float diffuse; };

void ReadLights(out LightData lights[2], float diffuse)
{
    lights[0].color = _LightColors[0];
    lights[0].diffuse = diffuse;
    lights[1].color = _LightColors[1];
    lights[1].diffuse = 0.5;
}
void AddLight(inout float3 sum, LightData light, float gain = 1.0)
{
    sum += light.color * light.diffuse * gain;
}
float3 ComputeLighting(PSInput input)
{
    float3 n = normalize(input.normalWS);
    float3 v = normalize(input.viewWS);
    LightData lights[2];
    ReadLights(lights, saturate(n.z));
    float3 color = 0.0;
    AddLight(color, lights[0]);
    AddLight(color, lights[1], 0.25);
    float edge = 1.0 - saturate(dot(n, v));
    return color + edge * edge * _RimStrength;
}
float4 main(PSInput input) : SV_Target
{
    float3 lighting = ComputeLighting(input);
    float3 color;
    color.xy = mul(_ColorMix, lighting.xy);
    color.z = lighting.z;
    return float4(color * _BaseColor.rgb, _BaseColor.a);
}
