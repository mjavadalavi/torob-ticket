<?php

namespace App\Http\Requests;

use Illuminate\Contracts\Validation\Rule;
use Illuminate\Foundation\Http\FormRequest;

class SearchWeeklyScheduleRequest extends FormRequest
{
    /**
     * Determine if the user is authorized to make this request.
     */
    public function authorize(): bool
    {
        return true;
    }

    /**
     * Get the validation rules that apply to the request.
     *
     * @return array<string, Rule|array|string>
     */
    public function rules(): array
    {
        return [
            'destination' => 'required|max:5',
            'source' => 'required|max:5',
            'datetime' => 'date_format:Y-m-d'
        ];
    }

    public function messages(): array
    {
        return [
            'datetime.required' => 'datetime must be required by format Y-m-d.',
            'destination.required' => 'destination must be required.',
            'source.required' => 'source must be required.',
        ];
    }
}
