<?php

namespace App\Http\Controllers\API;

use App\Classes\ProjectResource;
use App\Enums\Status;
use App\Enums\StatusCode;
use App\Http\Controllers\Controller;
use App\Http\Requests\ListWeeklyScheduleRequest;
use App\Http\Requests\StoreWeeklyScheduleRequest;
use App\Models\WeeklySchedule;
use Illuminate\Http\JsonResponse;
use Symfony\Component\HttpFoundation\Response;

class WeeklyScheduleController extends Controller
{
    /**
     * @OA\Get(
     *      path="/index",
     *      operationId="Lists",
     *      tags={"source", "destination", "terminals"},
     *      summary="Get list of source, destination or terminals ",
     *      description="Returns list of source, destination or terminals",
     *      @OA\Response(
     *          response=200,
     *          description="Successful operation",
     *          @OA\JsonResponse(ref="#/components/schemas/ProjectResource")
     *       ),
     *      @OA\Response(
     *          response=404,
     *          description="Not Found"
     *      )
     *     )
     */
    public function index(ListWeeklyScheduleRequest $request)
    {
        $data = null;
        if($request->validated()){
            switch ($request->input("actions")){
                case "terminals":
                    $data = WeeklySchedule::groupBy("source_city_id")->get("source_city_id");
                    break;
                case "destination":
                    $validated = $request->validate([
                        'destination' => 'required|string|max:5',
                    ],[
                        'destination.required' => 'destination must be required and lower than 5 char.'
                    ]);
                    if ($validated)
                        $data = WeeklySchedule::where("destination_city_id", "=", $request->input("destination"))->get("source_city_id");
                    else
                        return response()
                            ->json(['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Failed])
                            ->setStatusCode(Response::HTTP_BAD_REQUEST)
                            ->header('Content-Type', 'application/json');
                    break;
                case "source":
                    $validated = $request->validate([
                        'destination' => 'required|string|max:5',
                    ],[
                        'destination.required' => 'destination must be required and lower than 5 char.'
                    ]);
                    if ($validated)
                        $data = WeeklySchedule::where("source_terminal_id","=",$request->input("source"))->get("source_city_id", "source_terminal_id");
                    else
                        return response()
                            ->json(['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Failed])
                            ->setStatusCode(Response::HTTP_BAD_REQUEST)
                            ->header('Content-Type', 'application/json');
                    break;
            }
            if ($data == null)
                return response()
                    ->json(['status' => Status::Failed , "code" => StatusCode::Failed])
                    ->header('Content-Type', 'application/json');
            else
                return (new ProjectResource($data))
                        ->response()
                        ->header('Content-Type', 'application/json');
        }else{
            return response()
                ->json(['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Failed])
                ->setStatusCode(Response::HTTP_BAD_REQUEST)
                ->header('Content-Type', 'application/json');
        }
    }

    /**
     * @OA\Post(
     *      path="/weekly-schedule",
     *      operationId="storeweeklyschedule",
     *      tags={"WeeklySchedule"},
     *      summary="Store new WeeklySchedule",
     *      description="Returns json of result storing data",
     *      @OA\RequestBody(
     *          required=true,
     *          @OA\JsonContent(ref="#/components/schemas/StoreWeeklyScheduleRequest")
     *      ),
     *      @OA\Response(
     *          response=201,
     *          description="Successful operation",
     *          @OA\JsonContent(ref="#/components/schemas/WeeklySchedule")
     *       ),
     *      @OA\Response(
     *          response=400,
     *          description="Bad Request"
     *      )
     * )
     */
    public function store(StoreWeeklyScheduleRequest $request): JsonResponse
    {
        if ($request->validated()) {
            $weekly_schedule = WeeklySchedule::create($request->all());

            return (new ProjectResource($weekly_schedule))
                ->response()
                ->setStatusCode(Response::HTTP_CREATED)
                ->header('Content-Type', 'application/json');
        }else{
            return response()
                ->json(['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Failed])
                ->setStatusCode(Response::HTTP_BAD_REQUEST)
                ->header('Content-Type', 'application/json');
        }
    }
}
