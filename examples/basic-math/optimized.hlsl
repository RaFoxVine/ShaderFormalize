struct SurfaceInput
{
    float3 tint : COLOR0;
    float height : TEXCOORD0;
};

float3 BoundColor(float3 tint)
{
    return min(max(abs(tint), 0.0), 1.0);
}

float4 main(SurfaceInput input) : SV_Target
{
    float3 bounded = BoundColor(input.tint);
    float root = sqrt(max(input.height, 0.0));
    float radial = sqrt(root * root + 1.0);
    float separation = sqrt((root - 0.0) * (root - 0.0) + (1.0 - 0.0) * (1.0 - 0.0));
    float attenuation = 1.0 / (max(radial, separation) + 1.0);
    float softEdge = 1.0 / sqrt(root * root + 1.0);
    return float4((min(bounded, 1.0) * attenuation) * 0.5, softEdge);
}
