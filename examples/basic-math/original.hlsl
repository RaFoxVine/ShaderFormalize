struct SurfaceInput
{
    float3 tint : COLOR0;
    float height : TEXCOORD0;
};

float3 BoundColor(float3 tint)
{
    return clamp(abs(tint), 0.0, 1.0);
}

float4 main(SurfaceInput input) : SV_Target
{
    float3 bounded = BoundColor(input.tint);
    float root = sqrt(max(input.height, 0.0));
    float radial = length(float2(root, 1.0));
    float separation = distance(float2(root, 1.0), float2(0.0, 0.0));
    float attenuation = rcp(max(radial, separation) + 1.0);
    float softEdge = rsqrt(root * root + 1.0);
    float3 color = min(bounded, 1.0) * attenuation;
    return float4(color / 2.0, softEdge);
}
