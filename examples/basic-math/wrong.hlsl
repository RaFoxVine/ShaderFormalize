struct SurfaceInput
{
    float3 tint : COLOR0;
    float height : TEXCOORD0;
};
float3 BoundColor(float3 tint) { return clamp(abs(tint), 0.0, 1.0); }
float4 main(SurfaceInput input) : SV_Target
{
    float root = sqrt(max(input.height, 0.0));
    float radial = length(float2(root, 1.0));
    float separation = distance(float2(root, 1.0), float2(0.0, 0.0));
    float attenuation = rcp(max(radial, separation) + 1.0);
    return float4(min(BoundColor(input.tint), 1.0) * attenuation / 3.0, rsqrt(root * root + 1.0));
}
