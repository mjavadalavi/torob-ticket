<?php

namespace App\Http\Requests;

use Illuminate\Contracts\Validation\Rule;
use Illuminate\Foundation\Http\FormRequest;

class StoreReserveRequest extends FormRequest
{
    /**
     * Determine if the user is authorized to make this request.
     */
    public function authorize(): bool
    {
        return false;
    }

    /**
     * Get the validation rules that apply to the request.
     *
     * @return array<string, Rule|array|string>
     */
    public function rules(): array
    {
        return [
            'search_id' => 'required|string',
            'passenger_count' => 'required|int',
            'chairs' => 'required|array'
        ];
    }

    public function messages(): array
    {
        return [
            'search_id.required' => 'a str hash of searches values is required.',
            'passenger_count.required' => 'count of passenger is required.',
            'chairs.required' => 'an array of chairs.',
        ];
    }
}
