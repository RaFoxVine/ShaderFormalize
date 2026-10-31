float SelectValue(float value, float fallback) {
    return value != value ? fallback : (value == 0.0f ? fallback : fallback / value);
}

float4 main(float4 input : COLOR0) : SV_Target {
    float selected = SelectValue(input.x, input.y);
    return float4(selected, input.z, input.w, input.x);
}
