struct Payload
{
    float2 value : TEXCOORD0;
    float scale : TEXCOORD1;
};

cbuffer Parameters : register(b0)
{
    float bias;
    float2 multiplier;
};

float helper(float2 value, float scale)
{
    float result = value.x * scale + value.y;
    return sqrt(result) + scale;
}

float4 main(Payload payload, float4 other : COLOR0) : SV_Target
{
    float2 value = payload.value * multiplier;
    value += other.xy;
    float result = helper(value, payload.scale) + bias;
    bool selected = result >= 0 && payload.scale != 0;
    float magnitude = selected ? result : -result;
    return float4(magnitude, sqrt(magnitude), value.x, value.y);
}
