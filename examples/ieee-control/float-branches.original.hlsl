float SelectValue(float value, float fallback) {
    if (value != value) { return value; }
    if (value == 0.0f) { return fallback; }
    return fallback / value;
}

float4 main(float4 input : COLOR0) : SV_Target {
    float selected = SelectValue(input.x, input.y);
    return float4(selected, input.z, input.w, asfloat(asuint(input.x)));
}
